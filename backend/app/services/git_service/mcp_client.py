"""Owns the MCP connections to the GitHub MCP server (spawned via npx),
one subprocess per user because each user brings their own token. Sessions
are created lazily, reused while the token is unchanged, and torn down by
disconnect_all() from main.py's lifespan handler or by close_session()
when a user disconnects. This file knows nothing about prompts or routing
-- just the MCP session mechanics.

Each session lives inside its own background task: the stdio/session
context managers use anyio cancel scopes, which must be entered and exited
from the same task, and request handlers each run in a different one.

Tools are exposed as a plain-text directory rather than an OpenAI-style
`tools` schema: the configured proxy/model (gemini-3.1-flash-lite via
betterproxy.ai) doesn't reliably round-trip native function calling --
requests with `tools` attached come back with empty content and no
tool_calls even though the model clearly attempted something (non-zero
completion tokens). The same model handles a plain-text "TOOL_CALL: {...}"
protocol correctly (see llm_client.chat_with_text_tools), so that's what
we drive it with instead."""

import asyncio
import json
import os
import shutil
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class _Conn:
    def __init__(self, token: str):
        self.token = token
        self.session: ClientSession | None = None
        self.tool_directory: str | None = None
        self.ready = asyncio.Event()
        self.stop = asyncio.Event()
        self.error: Exception | None = None
        self.task: asyncio.Task | None = None


_conns: dict[str, _Conn] = {}
_lock = asyncio.Lock()


def _server_params(token: str) -> StdioServerParameters:
    # On Windows, "npx" resolves to npx.CMD, and asyncio's subprocess exec
    # doesn't apply PATHEXT resolution the way cmd.exe does -- resolve the
    # real path via shutil.which so spawning doesn't fail with WinError 2.
    npx_command = "npx"
    if sys.platform == "win32":
        npx_command = shutil.which("npx") or "npx"
    # `env` replaces the child process's entire environment rather than
    # extending it -- merge with the parent's so PATH/SystemRoot/etc.
    # survive (their absence crashes Node's crypto init on Windows, and
    # would also break npx's own node/npm lookup on any platform).
    return StdioServerParameters(
        command=npx_command,
        args=["-y", "@modelcontextprotocol/server-github"],
        env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token},
    )


async def _run(conn: _Conn) -> None:
    try:
        async with stdio_client(_server_params(conn.token)) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                conn.session = session
                conn.ready.set()
                await conn.stop.wait()
    except Exception as exc:
        conn.error = exc
    finally:
        conn.session = None
        conn.ready.set()


async def _close(conn: _Conn) -> None:
    conn.stop.set()
    if conn.task is not None:
        try:
            await conn.task
        except Exception:
            pass


async def _get_conn(user_id: str, token: str) -> _Conn:
    async with _lock:
        conn = _conns.get(user_id)
        if conn and (conn.token != token or conn.task.done()):
            await _close(conn)
            conn = None
        if conn is None:
            conn = _Conn(token)
            conn.task = asyncio.create_task(_run(conn))
            _conns[user_id] = conn
    await conn.ready.wait()
    if conn.session is None:
        async with _lock:
            if _conns.get(user_id) is conn:
                del _conns[user_id]
        raise RuntimeError("Failed to start the GitHub MCP server") from conn.error
    return conn


class VerificationError(Exception):
    pass


async def verify_repo(user_id: str, token: str, owner: str, repo: str) -> None:
    """Asks the GitHub MCP server, using this token, whether owner/repo
    exists and is visible to it. Raises VerificationError with a
    user-presentable message otherwise. Leaves the verified session open
    for reuse by the next git turn; drops it on failure."""
    try:
        conn = await _get_conn(user_id, token)
        result = await asyncio.wait_for(
            conn.session.call_tool("search_repositories", {"query": f"repo:{owner}/{repo}"}),
            timeout=60,
        )
    except Exception as exc:
        await close_session(user_id)
        raise VerificationError("Couldn't reach GitHub through the MCP server.") from exc

    text = "\n".join(block.text for block in result.content if block.type == "text")
    if result.isError:
        await close_session(user_id)
        raise VerificationError("GitHub rejected this token.")
    try:
        found = json.loads(text).get("total_count", 0) > 0
    except (ValueError, AttributeError):
        found = False
    if not found:
        await close_session(user_id)
        raise VerificationError(
            f"Repository {owner}/{repo} wasn't found, or the token doesn't have access to it."
        )


async def close_session(user_id: str) -> None:
    async with _lock:
        conn = _conns.pop(user_id, None)
    if conn:
        await _close(conn)


async def disconnect_all() -> None:
    async with _lock:
        conns = list(_conns.values())
        _conns.clear()
    for conn in conns:
        await _close(conn)


def _format_tool(tool) -> str:
    # The MCP Tool model's field is `inputSchema` (camelCase, matching the
    # wire protocol's JSON schema), not `input_schema`.
    schema = tool.inputSchema or {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    params = ", ".join(
        f"{name}{'' if name in required else '?'}: {info.get('type', 'any')}"
        for name, info in properties.items()
    )
    return f"- {tool.name}({params}): {tool.description or ''}"


async def get_tool_directory_text(user_id: str, token: str) -> str:
    """One line per tool -- name, parameters, description -- for the
    manual TOOL_CALL protocol prompt."""
    conn = await _get_conn(user_id, token)
    if conn.tool_directory is None:
        result = await conn.session.list_tools()
        conn.tool_directory = "\n".join(_format_tool(tool) for tool in result.tools)
    return conn.tool_directory


async def call_tool(user_id: str, token: str, name: str, arguments: dict) -> str:
    conn = await _get_conn(user_id, token)
    result = await conn.session.call_tool(name, arguments)
    parts = [block.text for block in result.content if block.type == "text"]
    return "\n".join(parts)

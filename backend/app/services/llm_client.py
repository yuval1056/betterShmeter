"""OpenAI-compatible proxy client. Provides two call shapes:

- chat(): an ordinary multi-turn completion.
- chat_with_text_tools(): a tool-calling loop driven entirely through plain
  message content (a "TOOL_CALL: {...}" line the model emits), not the
  API's native `tools` param -- see git_service/mcp_client.py for why.

Both shapes guard against blank completions (a proxy returning 200 with
empty content and no error) by retrying once and then falling back to a
fixed non-empty reply rather than letting emptiness propagate.
"""

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.core.config import settings

MAX_TOOL_ROUNDS = 6

_BLANK_COMPLETION_FALLBACK = "I wasn't able to generate a response just now. Could you try again?"
_TOO_MANY_STEPS_REPLY = (
    "I wasn't able to finish this within a reasonable number of steps. "
    "Could you rephrase or narrow down the request?"
)

_TOOL_CALL_RE = re.compile(r"TOOL_CALL:\s*", re.IGNORECASE)

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_TRAILING_CLOSE_RE = re.compile(r"\A.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_UNCLOSED_OPEN_RE = re.compile(r"<think>.*\Z", re.DOTALL | re.IGNORECASE)


def _strip_thinking(content: str) -> str:
    """Some reasoning-model proxies leak chain-of-thought straight into the
    completion content instead of separating it out -- either as a full
    <think>...</think> block, or (when the chat template implicitly opens
    the tag as part of the prompt, so only the model's continuation comes
    back) as leading text ending in a bare </think>. Strip either shape so
    raw reasoning never reaches the user. If the whole reply turns out to
    be unclosed reasoning with no real answer, this can leave an empty
    string -- callers treat that the same as a blank completion."""
    stripped = _THINK_BLOCK_RE.sub("", content)
    if stripped == content and "</think>" in content.lower():
        stripped = _THINK_TRAILING_CLOSE_RE.sub("", content, count=1)
    if "<think>" in stripped.lower() and "</think>" not in stripped.lower():
        stripped = _THINK_UNCLOSED_OPEN_RE.sub("", stripped)
    return stripped.strip()


@dataclass
class _ToolCallAttempt:
    raw: str
    tool: str | None = None
    arguments: dict | None = None
    error: str | None = None


def _find_tool_call(content: str) -> _ToolCallAttempt | None:
    """Looks for a `TOOL_CALL: {...}` marker anywhere in the reply. Returns
    None if the reply isn't attempting a tool call at all (i.e. it's
    terminal text for this round). Returns an attempt with `.error` set if
    a TOOL_CALL marker is present but the JSON after it is unusable, so the
    caller can nudge the model to reissue rather than crashing outright."""
    match = _TOOL_CALL_RE.search(content)
    if not match:
        return None

    remainder = content[match.end():].strip()
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(remainder)
    except json.JSONDecodeError as exc:
        return _ToolCallAttempt(raw=remainder, error=f"invalid JSON after TOOL_CALL: ({exc.msg})")

    if not isinstance(obj, dict) or not isinstance(obj.get("tool"), str):
        return _ToolCallAttempt(
            raw=remainder,
            error='JSON object must look like {"tool": "<name>", "arguments": {...}}',
        )

    arguments = obj.get("arguments")
    if not isinstance(arguments, dict):
        # Tolerate the model flattening arguments onto the top-level object
        # instead of nesting them under "arguments".
        arguments = {key: value for key, value in obj.items() if key != "tool"}

    return _ToolCallAttempt(raw=remainder, tool=obj["tool"], arguments=arguments)


class LLMClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.PROXY_API_KEY or "unused",
            base_url=settings.PROXY_BASE_URL,
        )

    async def _complete_once(self, messages: list[dict[str, str]]) -> str | None:
        response = await self._client.chat.completions.create(
            model=settings.PROXY_MODEL_NAME,
            messages=messages,
        )
        content = response.choices[0].message.content
        if content:
            content = _strip_thinking(content)
        return content if content and content.strip() else None

    async def _complete_with_blank_retry(self, messages: list[dict[str, str]]) -> str:
        content = await self._complete_once(messages)
        if content is None:
            content = await self._complete_once(messages)
        return content if content is not None else _BLANK_COMPLETION_FALLBACK

    async def chat(self, messages: list[dict[str, str]], system_prompt: str) -> str:
        """Ordinary multi-turn completion. `messages` excludes the system
        prompt -- it's prepended here."""
        full_messages = [{"role": "system", "content": system_prompt}, *messages]
        return await self._complete_with_blank_retry(full_messages)

    async def chat_with_text_tools(
        self,
        history: list[dict[str, str]],
        initial_system_prompt: str,
        followup_system_prompt: str,
        tool_executor: Callable[[str, dict], Awaitable[str]],
        max_rounds: int = MAX_TOOL_ROUNDS,
        tool_has_run: bool = False,
    ) -> str:
        """Drives a tool-calling loop through plain message content.

        `initial_system_prompt` is used for the first round (deciding
        whether/which tool to call). `followup_system_prompt` is used for
        every round after a tool has actually executed (turning a raw tool
        result into a natural-language answer, possibly chaining another
        call) -- these are kept as two distinct prompts by construction,
        not just by convention, since mixing them hurt output quality.

        `tool_executor(name, arguments)` performs the actual call (e.g. via
        an MCP session) and returns its raw text result.

        Any reply that doesn't contain a TOOL_CALL marker is treated as
        terminal text for the turn -- this covers final answers, requests
        for confirmation before a high-impact action, and clarifying
        questions alike, since the distinction between those is a matter of
        prompt wording, not loop mechanics.
        """
        # `tool_has_run` may start True when `history` already ends with a
        # TOOL_RESULT (a tool the caller executed itself), so the model goes
        # straight to explaining it.
        transcript: list[dict[str, str]] = list(history)

        for _ in range(max_rounds):
            system_prompt = followup_system_prompt if tool_has_run else initial_system_prompt
            full_messages = [{"role": "system", "content": system_prompt}, *transcript]
            content = await self._complete_with_blank_retry(full_messages)

            attempt = _find_tool_call(content)
            if attempt is None:
                return content.strip()

            transcript.append({"role": "assistant", "content": content})

            if attempt.error:
                transcript.append(
                    {
                        "role": "user",
                        "content": (
                            f"Your TOOL_CALL could not be used: {attempt.error}. "
                            'Reissue it as exactly one line: '
                            'TOOL_CALL: {"tool": "<tool name>", "arguments": {...}}'
                        ),
                    }
                )
                continue

            try:
                result = await tool_executor(attempt.tool, attempt.arguments or {})
            except Exception as exc:  # noqa: BLE001 -- surfaced to the model, not raised
                result = f"ERROR calling {attempt.tool}: {exc}"

            transcript.append(
                {"role": "user", "content": f"TOOL_RESULT for {attempt.tool}:\n{result}"}
            )
            tool_has_run = True

        return _TOO_MANY_STEPS_REPLY


llm_client = LLMClient()

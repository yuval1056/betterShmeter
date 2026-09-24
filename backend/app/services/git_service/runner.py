"""Drives one git-mode turn: fetch the live tool directory, build the two
git-mode prompts around it, and run the tool-calling loop. Public surface
is intentionally just this one function -- callers don't need to know
about MCP sessions or the wire protocol.

High-impact tools (see risk.py) are gated in code, not just by the
model's own compliance with the confirmation rule in the prompts:

1. When the model asks for one, it is NEVER executed in that turn. The exact
   call (tool + arguments) is stored as this user's pending action and a
   confirmation request is returned.
2. On a later turn, if the user's own message is an explicit go-ahead for that
   pending action, the *stored* call is executed as-is. It is not regenerated
   by the model -- a regenerated call (e.g. a file the model writes out again)
   would never match the stored one, and the user would be asked to confirm
   forever.

So a destructive action can never execute within a single inference or a
single HTTP request, and the user always approves the exact arguments that
are later executed."""

import json
import time

from app.services.git_service import mcp_client
from app.services.git_service.credentials import GitCredentials
from app.services.git_service.prompts import build_decide_prompt, build_explain_prompt
from app.services.git_service.risk import is_high_impact_tool
from app.services.git_service.secrets_guard import redact_secrets, redact_secrets_text
from app.services.llm_client import llm_client

_CONFIRMATION_REQUIRED_TEMPLATE = (
    'CONFIRMATION_REQUIRED: "{tool}" was NOT executed. It is a high-impact '
    "action and is now waiting for the user's confirmation. Do not claim it "
    "was done and do not call it again in this turn. Explain in plain "
    "language exactly what will happen (using the arguments below) and ask "
    "the user to reply to confirm.\nArguments: {arguments}"
)

_CONFIRMATION_CLASSIFIER_PROMPT = (
    "You check whether a user approved a pending action. Reply with exactly "
    "YES or NO. Reply YES only if the user's message is a clear, explicit "
    "go-ahead to perform the pending action as described (e.g. \"yes\", "
    "\"go ahead\", \"do it\", \"confirm\"). Reply NO if it is a question, a "
    "change of plan, a request to modify the action, a refusal, or anything "
    "unrelated."
)

# A pending action older than this is dropped rather than confirmed.
_PENDING_TTL_SECONDS = 15 * 60

# user_id -> (tool_name, arguments, created_at) awaiting confirmation.
# Module-level and in-process, matching this app's existing single-process
# assumption (see storage/repository.py's shared-connection comment).
_pending: dict[str, tuple[str, dict, float]] = {}


def _describe(tool_name: str, arguments: dict) -> str:
    """Short, secret-free summary of a call for the classifier."""
    shown = {k: (v if len(str(v)) <= 200 else str(v)[:200] + "...") for k, v in arguments.items()}
    return f"{tool_name} {json.dumps(shown, default=str)}"


async def _user_confirmed(pending: tuple[str, dict, float], user_message: str) -> bool:
    prompt = (
        f"Pending action: {_describe(pending[0], pending[1])}\n\n"
        f"User's latest message: {user_message}\n\n"
        "Did the user explicitly approve the pending action? Answer YES or NO."
    )
    answer = await llm_client.chat(
        [{"role": "user", "content": prompt}], system_prompt=_CONFIRMATION_CLASSIFIER_PROMPT
    )
    return answer.strip().upper().startswith("YES")


async def run_git_turn(
    user_id: str, restated_intent: str, creds: GitCredentials, user_message: str
) -> str:
    """`user_message` is the user's actual latest message (not the model's
    restatement) -- only that can approve a pending high-impact action."""
    tool_directory = await mcp_client.get_tool_directory_text(user_id, creds.token)
    decide_prompt = build_decide_prompt(tool_directory, restated_intent, creds.owner, creds.repo)
    explain_prompt = build_explain_prompt(tool_directory, restated_intent, creds.owner, creds.repo)

    async def call(tool_name: str, arguments: dict) -> str:
        # Redact on the way out (arguments GitHub receives) and on the way
        # back (the result the model sees and may quote in its reply) --
        # a secret could enter either direction independently of the other.
        result = await mcp_client.call_tool(
            user_id, creds.token, tool_name, redact_secrets(arguments, (creds.token,))
        )
        return redact_secrets_text(result, (creds.token,))

    async def execute_tool(tool_name: str, arguments: dict) -> str:
        if is_high_impact_tool(tool_name):
            _pending[user_id] = (tool_name, arguments, time.monotonic())
            return _CONFIRMATION_REQUIRED_TEMPLATE.format(
                tool=tool_name, arguments=redact_secrets(arguments, (creds.token,))
            )
        return await call(tool_name, arguments)

    # A pending action is decided on exactly once: whatever the user says now
    # either confirms it or discards it.
    pending = _pending.pop(user_id, None)
    if pending and time.monotonic() - pending[2] <= _PENDING_TTL_SECONDS:
        if await _user_confirmed(pending, user_message):
            tool_name, arguments, _ = pending
            try:
                result = await call(tool_name, arguments)
            except Exception as exc:  # noqa: BLE001 -- surfaced to the model, not raised
                result = f"ERROR calling {tool_name}: {exc}"
            call_line = "TOOL_CALL: " + json.dumps({"tool": tool_name, "arguments": arguments})
            return await llm_client.chat_with_text_tools(
                history=[
                    {"role": "user", "content": restated_intent},
                    {"role": "assistant", "content": call_line},
                    {"role": "user", "content": f"TOOL_RESULT for {tool_name}:\n{result}"},
                ],
                initial_system_prompt=decide_prompt,
                followup_system_prompt=explain_prompt,
                tool_executor=execute_tool,
                tool_has_run=True,
            )

    return await llm_client.chat_with_text_tools(
        history=[{"role": "user", "content": restated_intent}],
        initial_system_prompt=decide_prompt,
        followup_system_prompt=explain_prompt,
        tool_executor=execute_tool,
    )

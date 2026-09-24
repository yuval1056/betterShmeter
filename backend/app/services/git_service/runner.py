"""Drives one git-mode turn: fetch the live tool directory, build the two
git-mode prompts around it, and run the tool-calling loop. Public surface
is intentionally just this one function -- callers don't need to know
about MCP sessions or the wire protocol.

High-impact tools (see risk.py) are gated in code, not just by the
model's own compliance with the confirmation rule in the prompts: the
first time a given user's turn requests one, it is never executed --
instead a pending record is kept and a confirmation request is returned.
Execution only happens once a *later*, separate call to run_git_turn for
the same user requests the exact same tool and arguments again, which can
only happen after the user has sent another message. This guarantees a
destructive action can never execute within a single inference or a
single HTTP request, even if the model ignores the prompt-level rule."""

from app.services.git_service import mcp_client
from app.services.git_service.credentials import GitCredentials
from app.services.git_service.prompts import build_decide_prompt, build_explain_prompt
from app.services.git_service.risk import is_high_impact_tool
from app.services.git_service.secrets_guard import redact_secrets, redact_secrets_text
from app.services.llm_client import llm_client

_CONFIRMATION_REQUIRED_TEMPLATE = (
    'CONFIRMATION_REQUIRED: "{tool}" was NOT executed. It is a high-impact '
    "action and requires the user to explicitly confirm it in a separate "
    "message first. Do not claim it was done. Instead, explain in plain "
    "language exactly what you are about to do (using the arguments below) "
    "and ask the user to confirm before you try again.\nArguments: {arguments}"
)

# user_id -> (tool_name, arguments) awaiting confirmation. Module-level and
# in-process, matching this app's existing single-process assumption (see
# storage/repository.py's shared-connection comment). Cleared as soon as a
# matching confirmed call is executed, or overwritten if the user's next
# request asks for something different -- either way nothing stale lingers.
_pending_confirmations: dict[str, tuple[str, dict]] = {}


async def run_git_turn(user_id: str, restated_intent: str, creds: GitCredentials) -> str:
    tool_directory = await mcp_client.get_tool_directory_text(user_id, creds.token)
    decide_prompt = build_decide_prompt(tool_directory, restated_intent, creds.owner, creds.repo)
    explain_prompt = build_explain_prompt(tool_directory, restated_intent, creds.owner, creds.repo)

    async def execute_tool(tool_name: str, arguments: dict) -> str:
        if is_high_impact_tool(tool_name):
            pending = _pending_confirmations.get(user_id)
            if pending != (tool_name, arguments):
                _pending_confirmations[user_id] = (tool_name, arguments)
                return _CONFIRMATION_REQUIRED_TEMPLATE.format(
                    tool=tool_name, arguments=redact_secrets(arguments, (creds.token,))
                )
            del _pending_confirmations[user_id]

        # Redact on the way out (arguments GitHub receives) and on the way
        # back (the result the model sees and may quote in its reply) --
        # a secret could enter either direction independently of the other.
        result = await mcp_client.call_tool(
            user_id, creds.token, tool_name, redact_secrets(arguments, (creds.token,))
        )
        return redact_secrets_text(result, (creds.token,))

    history = [{"role": "user", "content": restated_intent}]
    return await llm_client.chat_with_text_tools(
        history=history,
        initial_system_prompt=decide_prompt,
        followup_system_prompt=explain_prompt,
        tool_executor=execute_tool,
    )

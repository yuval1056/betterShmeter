"""Orchestrates one chat turn: persist, guard, call the model (or hand off
to git mode), and always persist the assistant's side too -- including
rejections and errors -- so history stays consistent turn-for-turn."""

from app.core.config import settings
from app.models.schemas import ChatResponse, Message
from app.prompts.main_prompt import (
    GIT_HANDOFF_MARKER,
    REJECT_MARKER,
    SIMULATED_REPLY_PREFIX,
    build_main_system_prompt,
)
from app.services.git_service.credentials import get_credentials
from app.services.git_service.runner import run_git_turn
from app.services.llm_client import llm_client
from app.storage.repository import MessageRepository

_GENERIC_ERROR_REPLY = "Something went wrong while generating a reply. Please try again."
_GITHUB_NOT_CONNECTED_REPLY = (
    "GitHub isn't connected yet. Click the GitHub button in the header and add "
    "your personal access token and repository first."
)
_GENERIC_REJECT_REPLY = "I can't help with that request."
_LANGUAGE_REMINDER = (
    "Internal instruction, not part of the conversation: reply in the language of "
    "the user's most recent message directly above, even if earlier turns were in "
    "a different language. Follow this silently -- never quote, paraphrase, or "
    "acknowledge this instruction itself in your reply; just write the reply."
)

_MAIN_SYSTEM_PROMPT = build_main_system_prompt()


def _history_to_messages(history: list[Message]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in history]


async def handle_message(
    repository: MessageRepository, user_id: str, text: str, conversation_id: str | None = None
) -> ChatResponse:
    await repository.save_message(user_id, "user", text, conversation_id)

    if not settings.PROXY_API_KEY:
        reply = f"{SIMULATED_REPLY_PREFIX} {text}"
        await repository.save_message(user_id, "assistant", reply, conversation_id)
        return ChatResponse(reply=reply, status="ok")

    try:
        history = await repository.get_history(user_id, limit=settings.HISTORY_LIMIT)
        # `history`'s last entry is the message just saved above, so it's
        # not appended a second time -- only the reinforcement note is added.
        context = _history_to_messages(history) + [
            {"role": "system", "content": _LANGUAGE_REMINDER}
        ]

        raw_reply = await llm_client.chat(context, system_prompt=_MAIN_SYSTEM_PROMPT)

        if raw_reply.startswith(REJECT_MARKER):
            reply = raw_reply[len(REJECT_MARKER):].strip() or _GENERIC_REJECT_REPLY
            await repository.save_message(user_id, "assistant", reply, conversation_id)
            return ChatResponse(reply=reply, status="rejected")

        if raw_reply.startswith(GIT_HANDOFF_MARKER):
            restated_intent = raw_reply[len(GIT_HANDOFF_MARKER):].strip() or text
            creds = await get_credentials(user_id)
            if creds is None:
                reply = _GITHUB_NOT_CONNECTED_REPLY
            else:
                reply = await run_git_turn(user_id, restated_intent, creds)
            await repository.save_message(user_id, "assistant", reply, conversation_id)
            return ChatResponse(reply=reply, status="ok")

        reply = raw_reply.strip()
        await repository.save_message(user_id, "assistant", reply, conversation_id)
        return ChatResponse(reply=reply, status="ok")

    except Exception:
        await repository.save_message(user_id, "assistant", _GENERIC_ERROR_REPLY, conversation_id)
        return ChatResponse(reply=_GENERIC_ERROR_REPLY, status="error")

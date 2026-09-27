"""Redacts known secret values before they can leave the process toward
GitHub (tool-call arguments) or toward the user (confirmation previews and
tool results echoed back into a reply).

This does not stop the model from ever *seeing* a secret -- it already
can't reach local files like .env (see mcp_client.py's docstring: the only
tool surface is the GitHub MCP server, which talks to the remote repo over
the GitHub API, not the local filesystem). This is the fallback layer for
the case that check doesn't cover: a secret that reached the model some
other way (pasted into chat, or present in the repo's git history from
before it was gitignored) and that the model then tries to relay outward,
e.g. by pasting it into a new issue or a file it pushes."""

import json

from app.core.config import settings

_REDACTED = "[REDACTED_SECRET]"


def _known_secrets(extra: tuple[str, ...] = ()) -> list[str]:
    return [
        value
        for value in (settings.PROXY_API_KEY, *extra)
        if value
    ]


def redact_secrets_text(text: str, extra: tuple[str, ...] = ()) -> str:
    for secret in _known_secrets(extra):
        text = text.replace(secret, _REDACTED)
    return text


def redact_secrets(arguments: dict, extra: tuple[str, ...] = ()) -> dict:
    """Deep-redacts a tool-call arguments dict by round-tripping through
    JSON, so a secret nested at any depth or embedded inside a larger
    string is still caught, not just an exact top-level value match."""
    if not _known_secrets(extra):
        return arguments
    return json.loads(redact_secrets_text(json.dumps(arguments), extra))

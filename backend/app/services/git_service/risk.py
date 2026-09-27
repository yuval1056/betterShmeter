"""Classifies which GitHub MCP tools are high-impact (hard to reverse or
broad blast radius), independently of the model's own judgment.

`prompts._HIGH_IMPACT_RULE` already *asks* the model to hold off on these
and get confirmation first, but that's advisory text the model can ignore,
misread, or be argued out of via injected content. This module is the part
that actually matters: `runner.py` checks a tool name against
`is_high_impact_tool()` before it is allowed to execute at all, regardless
of what the model decided.

The exact tool names exposed by `@modelcontextprotocol/server-github` can
vary by version -- verify `HIGH_IMPACT_TOOLS` against a live
`mcp_client.get_tool_directory_text()` call after upgrading that package.
`_HIGH_IMPACT_KEYWORDS` is a safety net for tool names this list didn't
anticipate: it flags anything whose name reads as destructive even if it
isn't spelled out above, at the cost of occasionally flagging something
that isn't actually risky (a false positive here only costs one extra
confirmation round, so it's the safe direction to err in).
"""

HIGH_IMPACT_TOOLS: frozenset[str] = frozenset(
    {
        "merge_pull_request",
        "create_or_update_file",
        "push_files",
        "delete_file",
        "create_branch",
        "update_pull_request_branch",
        "create_pull_request_review",
        # Content-publishing tools: gated not because they're destructive,
        # but because they push text somewhere public with no human review
        # in between -- the same confirmation step doubles as a chance to
        # catch a leaked secret before it's posted (see secrets_guard.py).
        "create_issue",
        "add_issue_comment",
        "create_pull_request",
    }
)

_HIGH_IMPACT_KEYWORDS: tuple[str, ...] = (
    "merge",
    "delete",
    "remove",
    "push",
    "force",
    "close",
    "overwrite",
)


def is_high_impact_tool(tool_name: str) -> bool:
    lowered = tool_name.lower()
    if tool_name in HIGH_IMPACT_TOOLS:
        return True
    return any(keyword in lowered for keyword in _HIGH_IMPACT_KEYWORDS)

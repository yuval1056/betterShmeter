# Architecture

## Repository layout

```
Better_Shmeter2/
├── README.md               Setup, run, API overview
├── ARCHITECTURE.md         This file
├── frontend/
│   ├── index.html          Single-page chat UI + all JS (fetches the API)
│   └── style.css
└── backend/
    ├── requirements.txt
    ├── .env.example        Template for secrets/config (real .env is gitignored)
    ├── data/               SQLite files, created at runtime (gitignored)
    └── app/
        ├── main.py                 App factory: lifespan, CORS, router
        ├── core/config.py          Settings loaded from .env (pydantic-settings)
        ├── api/
        │   └── routes.py           HTTP endpoints (thin, no business logic)
        │                           + get_repository dependency
        ├── models/schemas.py       Pydantic request/response/message models
        ├── prompts/main_prompt.py  Main system prompt + marker constants
        ├── services/
        │   ├── chat_service.py     Orchestrates one chat turn
        │   ├── llm_client.py       OpenAI-compatible client + text tool loop
        │   └── git_service/        GitHub mode (see below)
        └── storage/
            ├── db.py               SQLite connection + schema for messages
            └── repository.py       MessageRepository (async, lock-protected)
```

Dependencies point one way: `api → services → storage / core / models`.
Routes never touch the database or the LLM directly.

## Layers

| Layer     | Responsibility                                              |
| --------- | ----------------------------------------------------------- |
| `api`     | Parse requests, call a service, map failures to HTTP errors |
| `services`| All business logic: guarding, LLM calls, GitHub agent       |
| `storage` | Persistence only; knows nothing about LLMs or prompts       |
| `prompts` | Prompt text and the markers used to parse model output      |
| `core`    | Configuration                                               |

## Request flow: `POST /api/chat`

```
Browser ──► routes.post_chat ──► chat_service.handle_message
                                      │
        1. save the user message ─────┤
        2. no PROXY_API_KEY? ─────────┼─► save + return "[simulated reply]"
        3. load last N messages ──────┤   (HISTORY_LIMIT, default 10)
        4. llm_client.chat(main system prompt)
        5. inspect the reply prefix:
              SHMETER_REJECT:       ─► status "rejected", refusal text
              SHMETER_GIT_HANDOFF:  ─► git mode (below)
              anything else         ─► normal answer
        6. save the assistant message (always, even on reject/error)
        7. return {reply, status}
```

The first model call acts as a **router and guardrail in one**: the main prompt
tells the model to emit a marker prefix to reject a request or to hand it off to
git mode. The marker strings live in
[prompts/main_prompt.py](backend/app/prompts/main_prompt.py) next to the prompt,
so the wording and the parsing cannot drift apart.

Any unexpected exception inside a turn is caught, a generic error reply is saved,
and the response has `status: "error"`, so history stays consistent turn for turn.

## Git mode (`services/git_service/`)

Entered when the main model replies with the handoff marker and the user has
credentials.

| File                | Role                                                                                   |
| ------------------- | -------------------------------------------------------------------------------------- |
| `runner.py`         | Entry point `run_git_turn`. Builds prompts, runs the tool loop, enforces confirmation  |
| `prompts.py`        | Two prompts: "decide what to call" and "explain the result" (kept separate on purpose) |
| `mcp_client.py`     | One GitHub MCP subprocess per user; lazy start, reuse, teardown                        |
| `risk.py`           | Which tools are high impact (explicit list plus keyword safety net)                    |
| `secrets_guard.py`  | Redacts known secrets from tool arguments and results                                  |
| `credentials.py`    | Per-user token/owner/repo in `github.db`; falls back to `.env` values                  |

### Text-based tool calling

The proxy model does not reliably support native function calling, so tools are
described in plain text and the model calls one by emitting a single line:

```
TOOL_CALL: {"tool": "<name>", "arguments": {...}}
```

`LLMClient.chat_with_text_tools` runs the loop (max 6 rounds): call the model,
parse a `TOOL_CALL`, execute it, feed back a `TOOL_RESULT`, repeat until the model
answers in plain text. Malformed calls get a corrective message instead of a crash.

### High-impact action gate

Confirmation is enforced **in code**, not just requested in the prompt:

1. The model requests a high-impact tool (merge, push, delete, create issue/PR...).
2. `runner.py` does **not** execute it. It stores `(tool, arguments)` as pending for
   that user and returns a `CONFIRMATION_REQUIRED` result, so the model asks the user.
3. Only if a **later** turn requests the identical tool and arguments is it executed.

A destructive action therefore cannot run within one request, even if the model
ignores its instructions.

### Secret handling

`secrets_guard` replaces the LLM key, the server GitHub token and the user's token
with `[REDACTED_SECRET]` both **outbound** (arguments sent to GitHub) and **inbound**
(results shown to the model and user).

## Storage

Two SQLite databases under `backend/data/` (gitignored):

| File         | Table                | Contents                                        |
| ------------ | -------------------- | ----------------------------------------------- |
| `shmeter.db` | `messages`           | Chat turns per `user_id` (WAL mode)             |
| `github.db`  | `github_credentials` | Per-user token, owner, repo (**plain text**)    |

`MessageRepository` is created once at startup and shared by all requests. Its lock
serializes writes on the single SQLite connection, and blocking calls run in
`asyncio.to_thread` so the event loop is never blocked. Both databases migrate
older files by adding the `conversation_id` column if missing.

## Frontend

A single static page, [frontend/index.html](frontend/index.html), with inline
JavaScript and [style.css](frontend/style.css). No build step. It calls the API at
`API_BASE` (`http://localhost:8000/api`) for chat, history and GitHub connection.

## Key design decisions

- **Marker-based routing** in one model call keeps guardrails and routing together.
- **Text tool protocol** instead of native tools, because the proxy model does not support them reliably.
- **Code-level confirmation gate**, since prompt rules alone can be bypassed.
- **Per-user MCP subprocesses**, because each user supplies their own token.
- **Blank-completion retry and `<think>` stripping** in `llm_client` protect against proxy quirks.

## Known constraints

- Single process only: the write lock, pending confirmations and MCP sessions are in memory.
- On Windows, run without `--reload` or multiple workers (needed for asyncio subprocesses).
- Requires Node.js (`npx`) for the GitHub MCP server.
- User GitHub tokens are stored unencrypted.

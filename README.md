# Better Shmeter

A guarded chat assistant with an optional GitHub mode. You chat with it like any
LLM assistant; when your message is about your connected GitHub repository
(files, commits, branches, issues, pull requests), it hands the request to a
tool-calling agent that talks to GitHub through the official GitHub MCP server.

- **Guardrails first:** every message passes through a system prompt that rejects
  prompt-injection and jailbreak attempts before anything else happens.
- **Safe GitHub actions:** high-impact actions (merge, push, delete, create issue/PR...)
  are blocked in code until you confirm them in a separate message.
- **Secret redaction:** known secrets (API key, GitHub token) are stripped from
  anything sent to GitHub or shown back to you.
- **Per-user history and credentials**, stored in local SQLite files.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the code is organized.

## Tech stack

| Layer    | Tech                                                        |
| -------- | ----------------------------------------------------------- |
| Backend  | Python, FastAPI, Uvicorn, Pydantic                          |
| LLM      | Any OpenAI-compatible proxy (via the `openai` SDK)          |
| GitHub   | `@modelcontextprotocol/server-github` over MCP (stdio, npx) |
| Storage  | SQLite (WAL mode)                                           |
| Frontend | React + TypeScript (Vite)                                   |

## Prerequisites

- Python 3.11+
- Node.js (builds the frontend, and `npx` launches the GitHub MCP server)
- An API key for an OpenAI-compatible LLM endpoint (optional, see below)
- A GitHub personal access token (only for GitHub mode)

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # Linux/macOS: cp .env.example .env
```

Then edit `backend/.env`:

| Variable                       | Purpose                                                        |
| ------------------------------ | -------------------------------------------------------------- |
| `PROXY_API_KEY`                | LLM key. If empty, the app returns `[simulated reply]` instead |
| `PROXY_BASE_URL`               | OpenAI-compatible endpoint                                     |
| `PROXY_MODEL_NAME`             | Model to use                                                   |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Optional server-wide GitHub fallback token                     |
| `GITHUB_OWNER`, `GITHUB_REPO`  | Repository for that fallback token                             |
| `CORS_ORIGINS`                 | Allowed frontend origins, comma-separated                      |

Users can also connect their own token and repo from the GitHub button in the UI;
that takes priority over the `.env` fallback.

## Run

Backend (from `backend/`):

```bash
uvicorn app.main:app --port 8000
```

> Do **not** use `--reload` or `--workers` on Windows. Uvicorn then switches to an
> event loop that cannot spawn the subprocess the GitHub MCP server needs.

Frontend (from `frontend/`, in a second terminal):

```bash
npm install
npm run dev
```

Open http://localhost:3000. The frontend calls the API at `http://localhost:8000/api`
(override with `VITE_API_BASE`, see [frontend/src/api.ts](frontend/src/api.ts)); its origin must be listed in `CORS_ORIGINS`.

## API

All routes are under `/api`.

| Method | Path                     | Description                                   |
| ------ | ------------------------ | --------------------------------------------- |
| GET    | `/health`                | Liveness check                                |
| POST   | `/chat`                  | Send a message, get `{reply, status}`         |
| GET    | `/history/{user_id}`     | Fetch a user's message history                |
| DELETE | `/history/{user_id}`     | Clear a user's history                        |
| POST   | `/github/connect`        | Verify and save a user's token + repo         |
| GET    | `/github/status/{user_id}` | Whether the user has GitHub connected       |
| DELETE | `/github/{user_id}`      | Disconnect GitHub                             |

`status` in a chat response is `ok`, `rejected` (guardrail refusal) or `error`.
Interactive docs are at http://localhost:8000/docs while the server runs.

## Security notes

- Never commit `backend/.env`. It is gitignored; only `.env.example` is tracked.
- User GitHub tokens are stored **in plain text** in `backend/data/github.db`
  (gitignored). Treat that file like a secret.
- Data files under `backend/data/` are local runtime state, not source.

import type { ChatResponse, GithubStatus } from "./types";

// Backend base URL. Override with VITE_API_BASE; the frontend origin must be
// listed in the backend's CORS_ORIGINS.
const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

export class NetworkError extends Error {}

export class HttpError extends Error {
  constructor(
    public status: number,
    public detail?: string,
  ) {
    super(`HTTP ${status}`);
  }
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new NetworkError("Couldn't reach the server");
  }
}

function postJson(path: string, body: unknown): Promise<Response> {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const uid = encodeURIComponent;

export async function sendChat(userId: string, conversationId: string, message: string): Promise<ChatResponse> {
  const res = await postJson("/chat", { user_id: userId, conversation_id: conversationId, message });
  if (!res.ok) throw new HttpError(res.status);
  return res.json();
}

export async function clearHistory(userId: string): Promise<void> {
  try {
    await request(`/history/${uid(userId)}`, { method: "DELETE" });
  } catch {
    // ignore -- the UI clears regardless
  }
}

export async function getGithubStatus(userId: string): Promise<GithubStatus | null> {
  try {
    const res = await request(`/github/status/${uid(userId)}`);
    return res.ok ? await res.json() : null;
  } catch {
    return null; // backend offline
  }
}

export async function connectGithub(
  userId: string,
  conversationId: string,
  token: string,
  owner: string,
  repo: string,
): Promise<GithubStatus> {
  const res = await postJson("/github/connect", {
    user_id: userId,
    conversation_id: conversationId,
    token,
    owner,
    repo,
  });
  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep the generic message
    }
    throw new HttpError(res.status, detail);
  }
  return res.json();
}

export async function disconnectGithub(userId: string): Promise<void> {
  try {
    await request(`/github/${uid(userId)}`, { method: "DELETE" });
  } catch {
    // ignore
  }
}

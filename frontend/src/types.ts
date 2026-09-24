export type Role = "user" | "assistant";
export type ChatStatus = "ok" | "rejected" | "error";

export interface ChatMessage {
  id: number;
  role: Role;
  text: string;
  /** Extra CSS class: a ChatStatus, or "network-error". */
  variant?: string;
  time: Date;
}

export interface ChatResponse {
  reply: string;
  status: ChatStatus;
}

export interface GithubStatus {
  connected: boolean;
  owner?: string;
  repo?: string;
}

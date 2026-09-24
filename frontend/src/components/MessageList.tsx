import { useEffect, useRef } from "react";
import { BotIcon, ChatIcon, UserIcon } from "./Icons";
import type { ChatMessage, Role } from "../types";

function formatTime(date: Date): string {
  try {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function Avatar({ role }: { role: Role }) {
  return (
    <div className="avatar" aria-hidden="true">
      {role === "user" ? <UserIcon /> : <BotIcon />}
    </div>
  );
}

interface Props {
  messages: ChatMessage[];
  loading: boolean;
}

export default function MessageList({ messages, loading }: Props) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading]);

  return (
    <main ref={ref} className="messages" aria-live="polite">
      {messages.length === 0 && !loading && (
        <div className="empty-state">
          <div className="empty-icon" aria-hidden="true">
            <ChatIcon />
          </div>
          <h2>Start a conversation</h2>
          <p>Ask a question, or ask about the connected GitHub repo. Your history is saved automatically.</p>
        </div>
      )}
      {messages.map((m) => (
        <div key={m.id} className={"msg-row " + m.role}>
          <Avatar role={m.role} />
          <div className="msg-group">
            <div className={"msg " + m.role + (m.variant ? " " + m.variant : "")}>{m.text}</div>
            <div className="msg-timestamp">{formatTime(m.time)}</div>
          </div>
        </div>
      ))}
      {loading && (
        <div className="msg-row assistant">
          <Avatar role="assistant" />
          <div className="msg-group">
            <div className="msg assistant loading">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

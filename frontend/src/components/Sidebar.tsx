import { TrashIcon } from "./Icons";
import type { ConversationSummary } from "../types";

interface Props {
  conversations: ConversationSummary[];
  activeId: string;
  /** Mobile only: whether the drawer is slid open. */
  open: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onClose: () => void;
}

export default function Sidebar({ conversations, activeId, open, onSelect, onNew, onDelete, onClose }: Props) {
  return (
    <>
      <div className={"sidebar-backdrop" + (open ? " open" : "")} onClick={onClose} />
      <aside className={"sidebar" + (open ? " open" : "")} aria-label="Previous chats">
        <button className="new-chat-btn" type="button" onClick={onNew}>
          <span aria-hidden="true">+</span> New chat
        </button>
        <div className="sidebar-title">Chats</div>
        <nav className="conv-list">
          {conversations.length === 0 && <div className="conv-empty">No previous chats yet.</div>}
          {conversations.map((c) => (
            <div key={c.id} className={"conv-item" + (c.id === activeId ? " active" : "")}>
              <button className="conv-select" type="button" title={c.title} onClick={() => onSelect(c.id)}>
                {c.title}
              </button>
              <button
                className="conv-delete"
                type="button"
                title="Delete chat"
                aria-label={`Delete chat: ${c.title}`}
                onClick={() => onDelete(c.id)}
              >
                <TrashIcon />
              </button>
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}

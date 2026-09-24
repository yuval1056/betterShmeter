import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import Composer from "./components/Composer";
import GithubModal from "./components/GithubModal";
import Header from "./components/Header";
import MessageList from "./components/MessageList";
import Sidebar from "./components/Sidebar";
import { getOrCreateUserId, loadTheme, newId, saveTheme } from "./storage";
import type { Theme } from "./storage";
import type { ChatMessage, ConversationSummary, GithubStatus, Role } from "./types";

const userId = getOrCreateUserId();
const prefersDark = () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  // A chat is stored on the server after its first message; until then it's
  // just a fresh id, so "New chat" costs nothing.
  const [activeId, setActiveId] = useState(newId);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [online, setOnline] = useState(true);
  const [github, setGithub] = useState<GithubStatus>({ connected: false });
  const [modalOpen, setModalOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [focusSignal, setFocusSignal] = useState(0);
  const [theme, setTheme] = useState<Theme | null>(loadTheme);

  // Mirrors activeId so async work can tell if the user switched chats meanwhile.
  const activeIdRef = useRef(activeId);
  const nextId = useRef(0);

  const isDark = theme === "dark" || (theme === null && prefersDark());

  useEffect(() => {
    const root = document.documentElement;
    if (theme) root.setAttribute("data-theme", theme);
    else root.removeAttribute("data-theme");
  }, [theme]);

  const refreshConversations = useCallback(async () => {
    setConversations(await api.listConversations(userId));
  }, []);

  useEffect(() => {
    refreshConversations();
    api.getGithubStatus(userId).then((s) => s && setGithub(s));
  }, [refreshConversations]);

  const switchTo = useCallback((id: string, msgs: ChatMessage[]) => {
    activeIdRef.current = id;
    setActiveId(id);
    setMessages(msgs);
    setSidebarOpen(false);
    setFocusSignal((n) => n + 1);
  }, []);

  const addMessage = useCallback((role: Role, text: string, variant?: string) => {
    setMessages((m) => [...m, { id: nextId.current++, role, text, variant, time: new Date() }]);
  }, []);

  async function send(text: string) {
    if (loadingId !== null) return; // one message at a time, until it's answered
    const convId = activeIdRef.current;
    addMessage("user", text);
    setLoadingId(convId);

    // Only touch the visible chat if the user is still looking at it.
    const reply = (role: Role, body: string, variant?: string) => {
      if (activeIdRef.current === convId) addMessage(role, body, variant);
    };

    try {
      const data = await api.sendChat(userId, convId, text);
      setOnline(true);
      reply("assistant", data.reply, data.status || "ok");
    } catch (err) {
      if (err instanceof api.NetworkError) {
        setOnline(false);
        reply("assistant", "Couldn't reach the server. Check your connection and try again.", "network-error");
      } else if (err instanceof api.HttpError) {
        setOnline(true);
        reply("assistant", `Something went wrong on the server (HTTP ${err.status}).`, "error");
      } else {
        reply("assistant", "Got an unreadable response from the server.", "error");
      }
    } finally {
      setLoadingId((cur) => (cur === convId ? null : cur));
      refreshConversations();
    }
  }

  function newChat() {
    switchTo(newId(), []);
  }

  async function openConversation(id: string) {
    if (id === activeIdRef.current) {
      setSidebarOpen(false);
      return;
    }
    try {
      const stored = await api.getConversation(userId, id);
      switchTo(
        id,
        stored.map((m) => ({ id: nextId.current++, role: m.role, text: m.content, time: new Date(m.created_at) })),
      );
    } catch {
      setOnline(false);
    }
  }

  async function deleteConversation(id: string) {
    if (!window.confirm("Delete this chat? This can't be undone.")) return;
    try {
      await api.deleteConversation(userId, id);
    } catch {
      return;
    }
    if (id === activeIdRef.current) newChat();
    refreshConversations();
  }

  function toggleTheme() {
    const next: Theme = isDark ? "light" : "dark";
    setTheme(next);
    saveTheme(next);
  }

  const closeModal = useCallback(() => {
    setModalOpen(false);
    setFocusSignal((n) => n + 1);
  }, []);

  async function connect(token: string, owner: string, repo: string) {
    try {
      setGithub(await api.connectGithub(userId, activeIdRef.current, token, owner, repo));
    } catch (err) {
      if (err instanceof api.HttpError) throw new Error(err.detail ?? `Couldn't connect (HTTP ${err.status}).`);
      throw new Error("Couldn't reach the server.");
    }
    closeModal();
    addMessage("assistant", "GitHub connected. You can now ask me to work with your repository.");
  }

  async function disconnect() {
    await api.disconnectGithub(userId);
    setGithub({ connected: false });
    closeModal();
  }

  return (
    <>
      <div className="app-shell">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          open={sidebarOpen}
          onSelect={openConversation}
          onNew={newChat}
          onDelete={deleteConversation}
          onClose={() => setSidebarOpen(false)}
        />
        <div className="app">
          <Header
            online={online}
            github={github}
            isDark={isDark}
            onGithub={() => setModalOpen(true)}
            onToggleTheme={toggleTheme}
            onMenu={() => setSidebarOpen(true)}
          />
          <MessageList messages={messages} loading={loadingId === activeId} />
          <Composer onSend={send} focusSignal={focusSignal} busy={loadingId !== null} />
        </div>
      </div>
      <GithubModal open={modalOpen} status={github} onClose={closeModal} onConnect={connect} onDisconnect={disconnect} />
    </>
  );
}

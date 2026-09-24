import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "./api";
import Composer from "./components/Composer";
import GithubModal from "./components/GithubModal";
import Header from "./components/Header";
import MessageList from "./components/MessageList";
import { getOrCreateUserId, loadTheme, newId, saveTheme } from "./storage";
import type { Theme } from "./storage";
import type { ChatMessage, GithubStatus, Role } from "./types";

const userId = getOrCreateUserId();
const prefersDark = () => window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [online, setOnline] = useState(true);
  const [github, setGithub] = useState<GithubStatus>({ connected: false });
  const [modalOpen, setModalOpen] = useState(false);
  const [focusSignal, setFocusSignal] = useState(0);
  const [theme, setTheme] = useState<Theme | null>(loadTheme);

  // One id per conversation; a new one starts on page load and on Clear.
  const conversationId = useRef(newId());
  const nextId = useRef(0);

  const isDark = theme === "dark" || (theme === null && prefersDark());

  useEffect(() => {
    const root = document.documentElement;
    if (theme) root.setAttribute("data-theme", theme);
    else root.removeAttribute("data-theme");
  }, [theme]);

  // On page load: start with a clean history and fetch the GitHub status.
  useEffect(() => {
    api.clearHistory(userId);
    api.getGithubStatus(userId).then((s) => s && setGithub(s));
  }, []);

  const addMessage = useCallback((role: Role, text: string, variant?: string) => {
    setMessages((m) => [...m, { id: nextId.current++, role, text, variant, time: new Date() }]);
  }, []);

  async function send(text: string) {
    addMessage("user", text);
    setLoading(true);
    try {
      const data = await api.sendChat(userId, conversationId.current, text);
      setOnline(true);
      addMessage("assistant", data.reply, data.status || "ok");
    } catch (err) {
      if (err instanceof api.NetworkError) {
        setOnline(false);
        addMessage("assistant", "Couldn't reach the server. Check your connection and try again.", "network-error");
      } else if (err instanceof api.HttpError) {
        setOnline(true);
        addMessage("assistant", `Something went wrong on the server (HTTP ${err.status}).`, "error");
      } else {
        addMessage("assistant", "Got an unreadable response from the server.", "error");
      }
    } finally {
      setLoading(false);
    }
  }

  async function clear() {
    await api.clearHistory(userId);
    conversationId.current = newId();
    setMessages([]);
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
      setGithub(await api.connectGithub(userId, conversationId.current, token, owner, repo));
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
        <div className="app">
          <Header
            online={online}
            github={github}
            isDark={isDark}
            onGithub={() => setModalOpen(true)}
            onToggleTheme={toggleTheme}
            onClear={clear}
          />
          <MessageList messages={messages} loading={loading} />
          <Composer onSend={send} focusSignal={focusSignal} />
        </div>
      </div>
      <GithubModal open={modalOpen} status={github} onClose={closeModal} onConnect={connect} onDisconnect={disconnect} />
    </>
  );
}

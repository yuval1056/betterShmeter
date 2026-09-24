import { GithubIcon, SparkleIcon } from "./Icons";
import type { GithubStatus } from "../types";

interface Props {
  online: boolean;
  github: GithubStatus;
  isDark: boolean;
  onGithub: () => void;
  onToggleTheme: () => void;
  onMenu: () => void;
}

export default function Header({ online, github, isDark, onGithub, onToggleTheme, onMenu }: Props) {
  const ghTitle = github.connected ? `GitHub: ${github.owner} / ${github.repo}` : "Connect GitHub";
  return (
    <header className="app-header">
      <div className="app-header-title">
        <button className="icon-btn menu-btn" type="button" title="Chats" aria-label="Show chats" onClick={onMenu}>
          ☰
        </button>
        <div className="app-logo" aria-hidden="true">
          <SparkleIcon />
        </div>
        <div className="app-header-text">
          <h1>Better Shmeter</h1>
          <div className="app-subtitle">
            <span className="status-dot" aria-hidden="true" style={{ background: online ? "#4ade80" : "#f87171" }} />
            <span>{online ? "Connected" : "Offline"}</span>
          </div>
        </div>
      </div>
      <div className="header-actions">
        <button
          className={"icon-btn gh-btn" + (github.connected ? " connected" : "")}
          type="button"
          title={ghTitle}
          aria-label="Connect GitHub"
          onClick={onGithub}
        >
          <GithubIcon />
        </button>
        <button className="icon-btn" type="button" title="Toggle theme" aria-label="Toggle dark mode" onClick={onToggleTheme}>
          {isDark ? "☀️" : "🌙"}
        </button>
      </div>
    </header>
  );
}

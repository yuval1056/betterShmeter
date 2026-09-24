import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { GithubStatus } from "../types";

interface Props {
  open: boolean;
  status: GithubStatus;
  onClose: () => void;
  onConnect: (token: string, owner: string, repo: string) => Promise<void>;
  onDisconnect: () => void;
}

export default function GithubModal({ open, status, onClose, onConnect, onDisconnect }: Props) {
  const [token, setToken] = useState("");
  const [owner, setOwner] = useState("");
  const [repo, setRepo] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const tokenRef = useRef<HTMLInputElement>(null);

  // Reset the form each time the modal opens.
  useEffect(() => {
    if (!open) return;
    setError("");
    setToken("");
    setOwner(status.connected ? (status.owner ?? "") : "");
    setRepo(status.connected ? (status.repo ?? "") : "");
    tokenRef.current?.focus();
  }, [open, status]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await onConnect(token.trim(), owner.trim(), repo.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't connect.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={"modal-backdrop" + (open ? " open" : "")}
      role="dialog"
      aria-modal="true"
      aria-labelledby="gh-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <form className="modal" autoComplete="off" onSubmit={submit}>
        <h2 id="gh-title">Connect GitHub</h2>
        <p>
          Enter a{" "}
          <a href="https://github.com/settings/tokens" target="_blank" rel="noopener noreferrer">
            personal access token
          </a>{" "}
          (with <b>repo</b> scope), your GitHub username and the repository to work on. GitHub no longer accepts
          account passwords for API access, so a token is used instead. The details are verified through GitHub
          first, then saved in a local SQLite file on the server.
        </p>
        <label htmlFor="gh-token">Personal access token</label>
        <input
          id="gh-token"
          ref={tokenRef}
          type="password"
          placeholder="ghp_..."
          autoComplete="new-password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <label htmlFor="gh-owner">GitHub username / owner</label>
        <input
          id="gh-owner"
          type="text"
          placeholder="username or organization"
          required
          value={owner}
          onChange={(e) => setOwner(e.target.value)}
        />
        <label htmlFor="gh-repo">Repository</label>
        <input id="gh-repo" type="text" placeholder="my-repo" required value={repo} onChange={(e) => setRepo(e.target.value)} />
        <div className="modal-error" role="alert">
          {error}
        </div>
        <div className="modal-actions">
          {status.connected && (
            <button type="button" onClick={onDisconnect}>
              Disconnect
            </button>
          )}
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="primary" type="submit" disabled={busy}>
            {busy ? "Connecting..." : "Connect"}
          </button>
        </div>
      </form>
    </div>
  );
}

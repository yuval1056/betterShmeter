import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { SendIcon } from "./Icons";

interface Props {
  onSend: (text: string) => void;
  /** Bump to move focus back to the input (e.g. after closing a modal). */
  focusSignal: number;
}

export default function Composer({ onSend, focusSignal }: Props) {
  const [value, setValue] = useState("");
  const [sent, setSent] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState(-1);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, [focusSignal]);

  // Auto-grow up to 140px.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }, [value]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const text = value.trim();
    if (!text) return;
    setSent((s) => [...s, text]);
    setHistIdx(-1);
    setValue("");
    onSend(text);
  }

  // Up/Down arrows walk through previously sent messages.
  function navigate(delta: -1 | 1) {
    if (sent.length === 0) return;
    if (delta === -1) {
      const next = histIdx === -1 ? sent.length - 1 : Math.max(histIdx - 1, 0);
      setHistIdx(next);
      setValue(sent[next]);
    } else if (histIdx !== -1) {
      if (histIdx < sent.length - 1) {
        setHistIdx(histIdx + 1);
        setValue(sent[histIdx + 1]);
      } else {
        setHistIdx(-1);
        setValue("");
      }
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      navigate(-1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      navigate(1);
    }
  }

  return (
    <>
      <form className="chat-form" onSubmit={submit}>
        <div className="composer-wrap">
          <textarea
            ref={inputRef}
            rows={1}
            autoComplete="off"
            placeholder="Ask me anything, or about the connected GitHub repo..."
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={onKeyDown}
          />
        </div>
        <button className="send-btn" type="submit" title="Send" aria-label="Send message" disabled={!value.trim()}>
          <SendIcon />
        </button>
      </form>
      <div className="hint">
        Press <kbd>Enter</kbd> to send &middot; <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
      </div>
    </>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  onSend: (text: string) => void;
  onAbort: () => void;
  isStreaming: boolean;
  placeholder?: string;
};

export function ChatInput({
  onSend,
  onAbort,
  isStreaming,
  placeholder = "Ask about your business…",
}: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "." && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        if (isStreaming) onAbort();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isStreaming, onAbort]);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  }

  return (
    <div
      style={{
        position: "relative",
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-strong)",
        borderRadius: 12,
        padding: "var(--space-3) var(--space-4)",
        display: "flex",
        alignItems: "flex-end",
        gap: 8,
        transition: "border-color 100ms ease-out",
      }}
      onFocus={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor =
          "var(--accent)";
      }}
      onBlur={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor =
          "var(--border-strong)";
      }}
    >
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          const el = e.currentTarget;
          el.style.height = "auto";
          el.style.height = `${Math.min(el.scrollHeight, 144)}px`;
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        rows={1}
        placeholder={placeholder}
        aria-label="Message"
        style={{
          flex: 1,
          background: "transparent",
          border: 0,
          outline: "none",
          resize: "none",
          fontSize: 15,
          lineHeight: 1.5,
          color: "var(--text-primary)",
          maxHeight: 144,
          padding: 0,
        }}
      />
      {isStreaming ? (
        <button
          type="button"
          onClick={onAbort}
          aria-label="Stop streaming (Cmd+.)"
          title="Stop (Cmd+.)"
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: "var(--text-muted)",
            color: "var(--accent-fg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          ◼
        </button>
      ) : value.trim() ? (
        <button
          type="button"
          onClick={submit}
          aria-label="Send"
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: "var(--accent)",
            color: "var(--accent-fg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 16,
            transition: "background 150ms ease-out",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              "var(--accent-hover)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              "var(--accent)";
          }}
        >
          →
        </button>
      ) : null}
    </div>
  );
}

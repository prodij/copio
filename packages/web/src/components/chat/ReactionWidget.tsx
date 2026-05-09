"use client";

import { useState } from "react";
import { postReaction } from "@/lib/api";

const EMOJIS: Array<{ char: string; label: string }> = [
  { char: "👍", label: "Mark as positive gold-standard" },
  { char: "👎", label: "Flag for review and explain what was wrong" },
  { char: "🎯", label: "Mark as exactly right" },
  { char: "❓", label: "Mark as unclear" },
  { char: "🔁", label: "Mark as wrong, retry" },
];

type Props = { messageId: string };

export function ReactionWidget({ messageId }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [showInput, setShowInput] = useState(false);
  const [comment, setComment] = useState("");
  const [confirmation, setConfirmation] = useState<string | null>(null);

  async function pick(emoji: string) {
    setSelected(emoji);
    if (emoji === "👎") {
      setShowInput(true);
      return;
    }
    setShowInput(false);
    await postReaction(messageId, emoji);
    flashConfirmation();
  }

  async function submitComment(e: React.FormEvent) {
    e.preventDefault();
    await postReaction(messageId, "👎", comment.trim() || undefined);
    setShowInput(false);
    setComment("");
    flashConfirmation();
  }

  function flashConfirmation() {
    setConfirmation("Thanks — logged");
    window.setTimeout(() => setConfirmation(null), 2000);
  }

  return (
    <div style={{ marginTop: "var(--space-3)" }}>
      <div
        role="group"
        aria-label="React to this answer"
        style={{ display: "flex", gap: 4, flexWrap: "wrap" }}
      >
        {EMOJIS.map(({ char, label }) => {
          const active = selected === char;
          return (
            <button
              key={char}
              type="button"
              aria-label={label}
              aria-pressed={active}
              onClick={() => void pick(char)}
              style={{
                width: 40,
                height: 40,
                borderRadius: 8,
                fontSize: 22,
                background: active ? "rgba(0,122,255,0.10)" : "transparent",
                transition:
                  "background 200ms ease-out, transform 150ms ease-out",
                lineHeight: 1,
              }}
              onMouseDown={(e) => {
                (e.currentTarget as HTMLButtonElement).style.transform =
                  "scale(0.95)";
              }}
              onMouseUp={(e) => {
                (e.currentTarget as HTMLButtonElement).style.transform =
                  "scale(1)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.transform =
                  "scale(1)";
                if (!active) {
                  (e.currentTarget as HTMLButtonElement).style.background =
                    "transparent";
                }
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  (e.currentTarget as HTMLButtonElement).style.background =
                    "var(--bg-elevated)";
                }
              }}
            >
              {char}
            </button>
          );
        })}
      </div>
      {showInput && (
        <form
          onSubmit={submitComment}
          style={{ marginTop: "var(--space-2)" }}
        >
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Tell me what was wrong"
            autoFocus
            style={{
              width: "100%",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-strong)",
              borderRadius: 8,
              padding: "var(--space-3)",
              fontSize: 14,
              color: "var(--text-primary)",
              outline: "none",
            }}
          />
        </form>
      )}
      {confirmation && (
        <div
          style={{
            marginTop: "var(--space-2)",
            fontSize: 13,
            fontStyle: "italic",
            color: "var(--text-muted)",
          }}
          aria-live="polite"
        >
          {confirmation}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import type { Citation } from "@/lib/api";

type Props = { citation: Citation; index: number };

export function CitationPill({ citation, index }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline" }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <sup
        className="cite"
        tabIndex={0}
        aria-label={`Citation ${index}: ${citation.source}`}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
        }}
      >
        {index}
      </sup>
      {open && (
        <span
          role="dialog"
          aria-modal="false"
          style={{
            position: "absolute",
            bottom: "100%",
            left: 0,
            transform: "translateY(-8px)",
            zIndex: 30,
            width: 320,
            background: "var(--bg-base)",
            color: "var(--text-primary)",
            border: "1px solid var(--border-strong)",
            borderRadius: 12,
            padding: "var(--space-4)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
            fontSize: 13,
            lineHeight: 1.4,
            fontStyle: "normal",
          }}
        >
          <div style={{ fontWeight: 600, color: "var(--text-secondary)" }}>
            {citation.source}
          </div>
          {citation.detail && (
            <div
              style={{
                marginTop: 4,
                fontSize: 12,
                color: "var(--text-muted)",
              }}
            >
              {citation.detail}
            </div>
          )}
          {citation.preview && (
            <div
              style={{
                marginTop: 8,
                fontFamily:
                  "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                fontSize: 12,
                color: "var(--text-primary)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {citation.preview}
            </div>
          )}
          {citation.open_in_amazon_url && (
            <>
              <div
                style={{
                  borderTop: "1px solid var(--border-subtle)",
                  margin: "var(--space-3) calc(var(--space-4) * -1) 0",
                }}
              />
              <a
                href={citation.open_in_amazon_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-block",
                  marginTop: "var(--space-3)",
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--accent-text)",
                }}
              >
                Open in Amazon ↗
              </a>
            </>
          )}
        </span>
      )}
    </span>
  );
}

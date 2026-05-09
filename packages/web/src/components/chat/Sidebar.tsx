"use client";

import { useEffect, useState } from "react";
import {
  listCapabilities,
  listThreads,
  type Capability,
  type ThreadSummary,
} from "@/lib/api";
import { CapabilityRow } from "./CapabilityRow";

type Props = {
  founderName: string;
  activeThreadId: string | null;
  onNewDiagnostic: () => void;
  onSelectThread: (id: string) => void;
};

export function Sidebar({
  founderName,
  activeThreadId,
  onNewDiagnostic,
  onSelectThread,
}: Props) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);

  useEffect(() => {
    void Promise.all([listThreads(), listCapabilities()]).then(([t, c]) => {
      setThreads(t);
      setCapabilities(c);
    });
  }, []);

  return (
    <aside
      style={{
        width: 240,
        flexShrink: 0,
        background: "var(--bg-sidebar)",
        borderRight: "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        height: "100vh",
      }}
    >
      <div
        style={{
          padding: "var(--space-4)",
          fontFamily: "var(--font-display)",
          fontSize: 16,
          fontWeight: 500,
          letterSpacing: "-0.01em",
          color: "var(--text-primary)",
        }}
      >
        copio
      </div>

      <div style={{ padding: "0 var(--space-4) var(--space-4)" }}>
        <button
          type="button"
          onClick={onNewDiagnostic}
          style={{
            width: "100%",
            border: "1px solid var(--border-strong)",
            borderRadius: 8,
            padding: "var(--space-2) var(--space-3)",
            fontSize: 14,
            fontWeight: 600,
            color: "var(--accent-text)",
            background: "transparent",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            transition: "background 150ms ease-out",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              "var(--bg-elevated)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              "transparent";
          }}
        >
          <span aria-hidden>+</span>
          New diagnostic
        </button>
      </div>

      {capabilities.length > 0 && (
        <div style={{ padding: "var(--space-2) 0" }}>
          <SidebarSubhead label="Capabilities" />
          {capabilities.map((c) => (
            <CapabilityRow key={c.id} capability={c} />
          ))}
        </div>
      )}

      <div style={{ padding: "var(--space-2) 0", flex: 1, overflow: "auto" }}>
        <SidebarSubhead label="Threads" />
        {threads.length === 0 ? (
          <div
            style={{
              padding: "var(--space-2) var(--space-4)",
              fontSize: 12,
              color: "var(--text-muted)",
            }}
          >
            No diagnostics yet.
          </div>
        ) : (
          threads.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onSelectThread(t.id)}
              style={{
                width: "100%",
                textAlign: "left",
                padding: "var(--space-2) var(--space-4)",
                background:
                  activeThreadId === t.id
                    ? "var(--bg-elevated)"
                    : "transparent",
                transition: "background 100ms ease-out",
              }}
              onMouseEnter={(e) => {
                if (activeThreadId !== t.id) {
                  (e.currentTarget as HTMLButtonElement).style.background =
                    "rgba(245,245,247,0.5)";
                }
              }}
              onMouseLeave={(e) => {
                if (activeThreadId !== t.id) {
                  (e.currentTarget as HTMLButtonElement).style.background =
                    "transparent";
                }
              }}
            >
              <div
                style={{
                  fontSize: 14,
                  color: "var(--text-primary)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {t.title}
              </div>
              {t.preview && (
                <div
                  style={{
                    fontSize: 12,
                    color: "var(--text-muted)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {t.preview}
                </div>
              )}
            </button>
          ))
        )}
      </div>

      <div
        style={{
          height: 56,
          borderTop: "1px solid var(--border-subtle)",
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 var(--space-4)",
        }}
      >
        <div
          aria-hidden
          style={{
            width: 24,
            height: 24,
            borderRadius: "50%",
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 11,
            color: "var(--text-secondary)",
            fontWeight: 600,
          }}
        >
          {founderName.slice(0, 1).toUpperCase()}
        </div>
        <div
          style={{
            fontSize: 13,
            color: "var(--text-primary)",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            flex: 1,
          }}
        >
          {founderName}
        </div>
      </div>
    </aside>
  );
}

function SidebarSubhead({ label }: { label: string }) {
  return (
    <div
      style={{
        padding: "var(--space-2) var(--space-4)",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        color: "var(--text-muted)",
      }}
    >
      {label}
    </div>
  );
}

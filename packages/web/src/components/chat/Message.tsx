"use client";

import type { AssistantMessage, UserMessage } from "@/hooks/useDiagnostic";
import { PersonaAvatar } from "./PersonaAvatar";
import { ProseRenderer } from "./ProseRenderer";
import { ReactionWidget } from "./ReactionWidget";
import { StreamingSubState } from "./StreamingSubState";

type Props = {
  message: AssistantMessage | UserMessage;
  founderName: string;
  personaInitials: string;
  isFirstAssistant: boolean;
  currentSubState: string | null;
  isStreamingNow: boolean;
};

export function Message({
  message,
  founderName,
  personaInitials,
  isFirstAssistant,
  currentSubState,
  isStreamingNow,
}: Props) {
  if (message.role === "user") {
    return (
      <div
        style={{
          display: "flex",
          gap: 12,
          padding: "var(--space-6) 0",
        }}
      >
        <UserAvatar name={founderName} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <Header label={founderName} />
          <div className="prose-body">{message.content}</div>
        </div>
      </div>
    );
  }

  const showCaret = isStreamingNow && message.state === "streaming";
  const showInitialSubState =
    showCaret && message.content.length === 0 && currentSubState;

  return (
    <div
      style={{
        display: "flex",
        gap: 12,
        padding: "var(--space-6) 0",
        borderLeft: message.degraded
          ? "2px solid var(--degraded-rail)"
          : "2px solid transparent",
        paddingLeft: message.degraded ? "var(--space-4)" : 0,
      }}
    >
      <PersonaAvatar initials={personaInitials} />
      <div style={{ flex: 1, minWidth: 0 }}>
        {isFirstAssistant && <Header label="copio" />}
        {showInitialSubState ? (
          <StreamingSubState label={currentSubState!} />
        ) : (
          <ProseRenderer
            text={message.content}
            citations={message.citations}
            streaming={showCaret}
          />
        )}
        {showCaret && message.content.length > 0 && currentSubState && (
          <div
            style={{
              marginTop: "var(--space-2)",
              fontSize: 12,
              color: "var(--text-muted)",
              fontStyle: "italic",
            }}
          >
            {currentSubState}
          </div>
        )}
        {message.id && message.state !== "streaming" && (
          <ReactionWidget messageId={message.id} />
        )}
      </div>
    </div>
  );
}

function Header({ label }: { label: string }) {
  return (
    <div
      style={{
        fontSize: 14,
        fontWeight: 500,
        color: "var(--text-primary)",
        marginBottom: 6,
      }}
    >
      {label}
    </div>
  );
}

function UserAvatar({ name }: { name: string }) {
  return (
    <div
      aria-hidden
      style={{
        width: 32,
        height: 32,
        borderRadius: "50%",
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-subtle)",
        color: "var(--text-secondary)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 600,
        fontSize: 12,
        flexShrink: 0,
      }}
    >
      {name.slice(0, 2).toUpperCase()}
    </div>
  );
}

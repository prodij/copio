"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChatInput } from "@/components/chat/ChatInput";
import { EmptyHero } from "@/components/chat/EmptyHero";
import { Message } from "@/components/chat/Message";
import { Sidebar } from "@/components/chat/Sidebar";
import { useDiagnostic } from "@/hooks/useDiagnostic";

const FOUNDER_NAME = "James";
const PERSONA_INITIALS = "C"; // unnamed persona placeholder until 1.1 sprint

const EXAMPLE_QUESTIONS = [
  "Why are conversions down on my top SKU this week?",
  "Returns spiked yesterday. Why?",
  "Which SKUs need re-buying this week?",
];

const GREETING = "I read your Amazon overnight. Ask me anything.";

export default function ChatPage() {
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const { messages, streaming, send, abort, reset } = useDiagnostic({
    onThread: (id) => setActiveThreadId(id),
  });

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streaming.currentSubState]);

  const firstAssistantIdx = useMemo(
    () => messages.findIndex((m) => m.role === "assistant"),
    [messages],
  );

  function onNewDiagnostic() {
    reset();
    setActiveThreadId(null);
  }

  function onSelectThread(id: string) {
    setActiveThreadId(id);
    // Phase 1.0 simplification: selecting a thread starts a fresh session.
    // Phase 1.1 will load /api/v1/threads/:id and rehydrate.
    reset();
  }

  function onSend(text: string) {
    void send({ text, threadId: activeThreadId });
  }

  const showHero = messages.length === 0;

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <Sidebar
        founderName={FOUNDER_NAME}
        activeThreadId={activeThreadId}
        onNewDiagnostic={onNewDiagnostic}
        onSelectThread={onSelectThread}
      />
      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          background: "var(--bg-base)",
        }}
      >
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "0 var(--space-6)",
          }}
        >
          <div
            style={{
              maxWidth: 720,
              margin: "0 auto",
              minHeight: "100%",
              display: "flex",
              flexDirection: "column",
              justifyContent: showHero ? "center" : "flex-start",
              paddingBottom: "var(--space-8)",
            }}
          >
            {showHero ? (
              <EmptyHero
                personaInitials={PERSONA_INITIALS}
                greeting={GREETING}
                examples={EXAMPLE_QUESTIONS}
                onPick={(q) => onSend(q)}
              />
            ) : (
              messages.map((m, i) => (
                <Message
                  key={`${m.role}-${i}-${m.id || "draft"}`}
                  message={m}
                  founderName={FOUNDER_NAME}
                  personaInitials={PERSONA_INITIALS}
                  isFirstAssistant={i === firstAssistantIdx}
                  currentSubState={streaming.currentSubState}
                  isStreamingNow={
                    streaming.isStreaming && i === messages.length - 1
                  }
                />
              ))
            )}
          </div>
        </div>
        <div
          style={{
            padding: "var(--space-4) var(--space-6) var(--space-6)",
            borderTop: "1px solid var(--border-subtle)",
            background: "var(--bg-base)",
          }}
        >
          <div style={{ maxWidth: 720, margin: "0 auto" }}>
            <ChatInput
              onSend={onSend}
              onAbort={abort}
              isStreaming={streaming.isStreaming}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

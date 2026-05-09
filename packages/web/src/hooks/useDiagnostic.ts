"use client";

import { useCallback, useRef, useState } from "react";
import { apiUrl, type Citation } from "@/lib/api";

export type AssistantMessage = {
  id: string; // server-issued message_id (from reaction_anchor); empty until finish
  role: "assistant";
  content: string;
  citations: Citation[];
  subStates: string[];
  state: "streaming" | "complete" | "degraded" | "failed";
  degraded: boolean;
};

export type UserMessage = {
  id: string; // local-only id
  role: "user";
  content: string;
};

export type ChatMessage = UserMessage | AssistantMessage;

export type StreamingState = {
  isStreaming: boolean;
  currentSubState: string | null;
};

type SendArgs = { text: string; threadId: string | null };

export function useDiagnostic({
  onThread,
}: {
  onThread?: (threadId: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState<StreamingState>({
    isStreaming: false,
    currentSubState: null,
  });
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = null;
    setMessages([]);
    setStreaming({ isStreaming: false, currentSubState: null });
  }, []);

  const abort = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = null;
    setStreaming({ isStreaming: false, currentSubState: null });
  }, []);

  const send = useCallback(
    async ({ text, threadId }: SendArgs) => {
      const userMsg: UserMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
      };
      const draftAssistant: AssistantMessage = {
        id: "",
        role: "assistant",
        content: "",
        citations: [],
        subStates: [],
        state: "streaming",
        degraded: false,
      };

      setMessages((prev) => [...prev, userMsg, draftAssistant]);
      setStreaming({ isStreaming: true, currentSubState: null });

      const controller = new AbortController();
      abortRef.current = controller;

      const body = {
        thread_id: threadId,
        messages: [
          { role: "user", parts: [{ type: "text", text }] },
        ],
      };

      let response: Response;
      try {
        response = await fetch(apiUrl("/api/v1/chat"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(body),
          signal: controller.signal,
        });
      } catch (err) {
        finishWithError(setMessages, "Couldn't reach the server. Try again.");
        setStreaming({ isStreaming: false, currentSubState: null });
        return;
      }

      if (!response.ok || !response.body) {
        finishWithError(
          setMessages,
          `Server returned ${response.status}. Try again.`,
        );
        setStreaming({ isStreaming: false, currentSubState: null });
        return;
      }

      const newThreadId = response.headers.get("x-thread-id");
      if (newThreadId && newThreadId !== threadId) onThread?.(newThreadId);

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        let chunk: ReadableStreamReadResult<Uint8Array>;
        try {
          chunk = await reader.read();
        } catch (err) {
          break;
        }
        if (chunk.done) break;
        buffer += decoder.decode(chunk.value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          handleLine(line, setMessages, setStreaming);
        }
      }

      setStreaming({ isStreaming: false, currentSubState: null });
      abortRef.current = null;

      // Stream ended without a `finish` event — server probably crashed
      // mid-stream. Mark the in-flight assistant message as failed so the UI
      // doesn't sit on an empty bubble forever.
      setMessages((prev) =>
        updateLastAssistant(prev, (m) => {
          if (m.state !== "streaming") return m;
          return {
            ...m,
            content: m.content ||
              "The connection dropped before I could answer. Try again.",
            state: "failed",
          };
        }),
      );
    },
    [onThread],
  );

  return { messages, streaming, send, abort, reset };
}

function finishWithError(
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  errorText: string,
) {
  setMessages((prev) => {
    const next = [...prev];
    const lastIdx = next.length - 1;
    if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
      const assistant = { ...(next[lastIdx] as AssistantMessage) };
      assistant.content = errorText;
      assistant.state = "failed";
      next[lastIdx] = assistant;
    }
    return next;
  });
}

function handleLine(
  line: string,
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  setStreaming: React.Dispatch<React.SetStateAction<StreamingState>>,
) {
  const colonIdx = line.indexOf(":");
  if (colonIdx <= 0) return;
  const prefix = line.slice(0, colonIdx);
  const rest = line.slice(colonIdx + 1);
  if (prefix === "0") {
    let text: string;
    try {
      text = JSON.parse(rest);
    } catch {
      return;
    }
    if (typeof text !== "string") return;
    setMessages((prev) => updateLastAssistant(prev, (m) => ({
      ...m,
      content: m.content + text,
    })));
    return;
  }
  if (prefix === "2") {
    let parts: Array<Record<string, unknown>>;
    try {
      parts = JSON.parse(rest);
    } catch {
      return;
    }
    for (const part of parts) {
      handleAnnotation(part, setMessages, setStreaming);
    }
    return;
  }
}

function handleAnnotation(
  part: Record<string, unknown>,
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  setStreaming: React.Dispatch<React.SetStateAction<StreamingState>>,
) {
  const type = part.type as string | undefined;
  if (type === "sub_state") {
    const label = (part.label as string) ?? null;
    setStreaming((s) => ({ ...s, currentSubState: label }));
    setMessages((prev) =>
      updateLastAssistant(prev, (m) => ({
        ...m,
        subStates: label ? [...m.subStates, label] : m.subStates,
      })),
    );
  } else if (type === "citation") {
    const citation: Citation = {
      id: String(part.id ?? ""),
      label: String(part.label ?? ""),
      source: String(part.source ?? ""),
      detail: (part.detail as string | null) ?? null,
      preview: (part.preview as string | null) ?? null,
      open_in_amazon_url:
        (part.open_in_amazon_url as string | null) ?? null,
    };
    setMessages((prev) =>
      updateLastAssistant(prev, (m) => ({
        ...m,
        citations: [...m.citations, citation],
      })),
    );
  } else if (type === "reaction_anchor") {
    const id = String(part.message_id ?? "");
    setMessages((prev) =>
      updateLastAssistant(prev, (m) => ({ ...m, id })),
    );
  } else if (type === "finish") {
    const stateRaw = String(part.state ?? "COMPLETE");
    const degraded = Boolean(part.degraded);
    const state: AssistantMessage["state"] = stateRaw.startsWith("FAILED")
      ? "failed"
      : degraded
        ? "degraded"
        : "complete";
    setMessages((prev) =>
      updateLastAssistant(prev, (m) => ({ ...m, state, degraded })),
    );
    setStreaming({ isStreaming: false, currentSubState: null });
  } else if (type === "error") {
    const message = String(part.message ?? "Something went wrong.");
    setMessages((prev) =>
      updateLastAssistant(prev, (m) => ({
        ...m,
        content: m.content || message,
        state: "failed",
      })),
    );
    setStreaming({ isStreaming: false, currentSubState: null });
  }
}

function updateLastAssistant(
  prev: ChatMessage[],
  fn: (m: AssistantMessage) => AssistantMessage,
): ChatMessage[] {
  const next = [...prev];
  for (let i = next.length - 1; i >= 0; i--) {
    if (next[i].role === "assistant") {
      next[i] = fn(next[i] as AssistantMessage);
      break;
    }
  }
  return next;
}

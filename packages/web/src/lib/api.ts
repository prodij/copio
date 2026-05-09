"use client";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export const apiUrl = (path: string) =>
  path.startsWith("http") ? path : `${API_BASE}${path}`;

export type Capability = {
  id: string;
  label: string;
  status: "ready" | "syncing" | "reconnect" | "unavailable";
  detail?: string | null;
  reconnect_url?: string | null;
};

export type ThreadSummary = {
  id: string;
  title: string;
  preview?: string | null;
  updated_at: string;
};

export type Citation = {
  id: string;
  label: string;
  source: string;
  detail?: string | null;
  preview?: string | null;
  open_in_amazon_url?: string | null;
};

export async function listThreads(): Promise<ThreadSummary[]> {
  const r = await fetch(apiUrl("/api/v1/threads"), {
    cache: "no-store",
    credentials: "include",
  });
  if (!r.ok) return [];
  return (await r.json()) as ThreadSummary[];
}

export async function listCapabilities(): Promise<Capability[]> {
  const r = await fetch(apiUrl("/api/v1/capabilities"), {
    cache: "no-store",
    credentials: "include",
  });
  if (!r.ok) return [];
  return (await r.json()) as Capability[];
}

export async function postReaction(
  messageId: string,
  emoji: string,
  comment?: string,
): Promise<void> {
  await fetch(apiUrl("/api/v1/reactions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ message_id: messageId, emoji, comment }),
  });
}

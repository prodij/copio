import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { disconnectConnection, pauseConnection, reconnectConnection, resumeConnection, type ConnectionSummary } from "./api";
import { ConfirmAction } from "./ConfirmAction";
import type { useSyncAction } from "./useSyncAction";

type Action = ReturnType<typeof useSyncAction>;

/** Pause, resume, reconnect and disconnect, offered only where the connection's state allows them. */
export function ConnectionActions({ connection, action }: { connection: ConnectionSummary; action: Action }) {
  const [reconnecting, setReconnecting] = useState(false);
  const busy = action.pendingKey?.startsWith("connection:") ?? false;
  const { id, state } = connection;
  const canReconnect = state === "reconnect_needed" || state === "disconnected";
  return (
    <div className="space-y-2">
      <div role="group" aria-label="Connection controls" className="flex flex-wrap items-center gap-2">
        {state === "healthy" && (
          <ConfirmAction label="Pause syncing" question="Pause new syncs? Running work finishes first."
            pending={action.pendingKey === "connection:pause"}
            disabled={busy}
            onConfirm={() => action.act("connection:pause", () => pauseConnection(id), "Syncing paused.")} />
        )}
        {state === "paused" && (
          <ConfirmAction label="Resume syncing" question="Resume scheduled syncs?"
            pending={action.pendingKey === "connection:resume"}
            disabled={busy}
            onConfirm={() => action.act("connection:resume", () => resumeConnection(id), "Syncing resumed.")} />
        )}
        {canReconnect && !reconnecting && (
          <Button size="xs" variant="outline" disabled={busy} onClick={() => setReconnecting(true)}>Reconnect</Button>
        )}
        {state !== "disconnected" && (
          <ConfirmAction label="Disconnect" question="Disconnect? The stored credential is destroyed."
            pending={action.pendingKey === "connection:disconnect"}
            disabled={busy}
            onConfirm={() => action.act("connection:disconnect", () => disconnectConnection(id), "Disconnected. The stored credential was destroyed.")} />
        )}
      </div>
      {reconnecting && (
        <ReconnectForm busy={busy} onCancel={() => setReconnecting(false)}
          onSubmit={(token) => {
            setReconnecting(false);
            action.act("connection:reconnect", () => reconnectConnection(id, token), "Reconnected.");
          }} />
      )}
    </div>
  );
}

function ReconnectForm({ busy, onCancel, onSubmit }: { busy: boolean; onCancel: () => void; onSubmit: (token: string) => void }) {
  const [token, setToken] = useState("");
  return (
    <form className="max-w-sm space-y-2 rounded-md border border-border p-3"
      onSubmit={(e) => { e.preventDefault(); if (token.trim()) onSubmit(token.trim()); }}>
      <Label htmlFor="reconnect-token">New access token</Label>
      {/* A password field so the token isn't shown, autofilled or remembered by the browser. */}
      <Input id="reconnect-token" type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} />
      <div className="flex gap-2">
        <Button size="xs" type="submit" disabled={busy || !token.trim()}>Reconnect</Button>
        <Button size="xs" type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

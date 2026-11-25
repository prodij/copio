import { Badge } from "@/components/ui/badge";
import type { DatasetHealth } from "./api";
import { label } from "./format";

type Variant = "default" | "secondary" | "destructive" | "outline";

const CONNECTION: Record<string, Variant> = {
  healthy: "outline",
  paused: "secondary",
  reconnect_needed: "destructive",
  disconnected: "secondary",
};

export function ConnectionStateBadge({ state }: { state: string }) {
  return <Badge variant={CONNECTION[state] ?? "outline"}>{state === "reconnect_needed" ? "Reconnect needed" : capital(label(state))}</Badge>;
}

const FRESHNESS: Record<DatasetHealth["freshness"], { variant: Variant; text: string }> = {
  fresh: { variant: "outline", text: "Fresh" },
  stale: { variant: "destructive", text: "Stale" },
  never_synced: { variant: "secondary", text: "Never synced" },
  no_target: { variant: "outline", text: "No target" },
};

export function FreshnessBadge({ freshness }: { freshness: DatasetHealth["freshness"] }) {
  const { variant, text } = FRESHNESS[freshness];
  return <Badge variant={variant}>{text}</Badge>;
}

const RUN: Record<string, Variant> = {
  queued: "outline",
  running: "default",
  waiting: "secondary",
  succeeded: "outline",
  failed: "destructive",
  cancelled: "secondary",
};

export function RunStatusBadge({ status }: { status: string }) {
  return <Badge variant={RUN[status] ?? "outline"}>{capital(status)}</Badge>;
}

function capital(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

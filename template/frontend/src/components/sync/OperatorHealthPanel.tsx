import type { OperatorHealth } from "./api";
import { ago, duration } from "./format";

/** Only what needs attention, worst first. A quiet workspace gets one quiet line. */
export function attentionItems(h: OperatorHealth): string[] {
  const items: string[] = [];
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
  if (h.failed_runs_awaiting_action) items.push(`${plural(h.failed_runs_awaiting_action, "failed run needs", "failed runs need")} a retry or replay`);
  if (h.reconnect_needed_connections) items.push(`${plural(h.reconnect_needed_connections, "connection needs", "connections need")} reconnecting`);
  if (h.auth_failures_recent) items.push(`${plural(h.auth_failures_recent, "auth failure", "auth failures")} in the last day`);
  if (h.expired_leases) items.push(`${plural(h.expired_leases, "dataset has an expired worker lease", "datasets have expired worker leases")}`);
  if (h.rate_limited_recent) items.push(`${plural(h.rate_limited_recent, "run was rate limited", "runs were rate limited")} in the last day`);
  if (h.oldest_queued_age_s !== null && h.oldest_queued_age_s > 300) {
    items.push(`Oldest queued run has waited ${duration(h.oldest_queued_age_s)}${h.outbox_pending ? ` (${h.outbox_pending} not yet handed to the queue)` : ""}`);
  }
  if (h.oldest_unprocessed_raw_at) items.push(`Unpublished raw data since ${ago(h.oldest_unprocessed_raw_at)}`);
  return items;
}

export function OperatorHealthPanel({ health }: { health: OperatorHealth }) {
  const items = attentionItems(health);
  const stalest = health.oldest_unpublished;
  return (
    <section aria-labelledby="sync-attention" className="space-y-2 rounded-md border p-4 text-sm">
      <h2 id="sync-attention" className="font-medium">Needs attention</h2>
      {items.length ? (
        <ul className="list-disc space-y-1 pl-5">
          {items.map((i) => <li key={i}>{i}</li>)}
        </ul>
      ) : (
        <p className="text-muted-foreground">Nothing right now.</p>
      )}
      <p className="text-xs text-muted-foreground">
        {health.queued_runs} queued, {health.waiting_runs} waiting
        {stalest ? `; least current dataset: ${stalest.dataset}${stalest.covered_to ? `, complete up to ${ago(stalest.covered_to)}` : ", never synced"}` : ""}.
      </p>
    </section>
  );
}

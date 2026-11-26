import { type ConnectionSummary, type DatasetHealth, refreshDataset } from "./api";
import { FreshnessBadge, RunStatusBadge } from "./badges";
import { ConfirmAction } from "./ConfirmAction";
import { ago, duration, short, when } from "./format";
import type { useSyncAction } from "./useSyncAction";

function Lag({ d }: { d: DatasetHealth }) {
  if (d.lag_s === null) return <span className="text-muted-foreground">Nothing published yet</span>;
  const target = d.freshness_target_s === null ? "no target set" : `target ${duration(d.freshness_target_s)}`;
  return (
    <span>
      {duration(d.lag_s)} behind <span className="text-muted-foreground">({target})</span>
    </span>
  );
}

/** What else an operator should know about the dataset, worst first. */
function problems(d: DatasetHealth): string[] {
  const out: string[] = [];
  if (d.missing_periods.length) {
    const n = d.missing_periods.length;
    out.push(`${n} missing ${n === 1 ? "period" : "periods"}: ${d.missing_periods.map((p) => `${short(p.start)} – ${short(p.end)}`).join("; ")}`);
  }
  if (d.replay_backlog) out.push(`${d.replay_backlog} raw ${d.replay_backlog === 1 ? "page" : "pages"} saved but not published`);
  if (d.lease_expired) out.push("Worker lease expired");
  return out;
}

export function DatasetHealthTable({ connection, datasets, action }: {
  connection: ConnectionSummary;
  datasets: DatasetHealth[];
  action: ReturnType<typeof useSyncAction>;
}) {
  if (!datasets.length) {
    return <p className="text-sm text-muted-foreground">No datasets yet. They appear once a schedule is set or a first sync runs.</p>;
  }
  const blocked = connection.state !== "healthy" ? `The connection is ${connection.state.replaceAll("_", " ")}` : undefined;
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th className="py-2 pr-3 font-medium">Dataset</th>
            <th className="py-2 pr-3 font-medium">Freshness</th>
            <th className="py-2 pr-3 font-medium">Complete through</th>
            <th className="py-2 pr-3 font-medium">Last attempt</th>
            <th className="py-2 font-medium"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {datasets.map((d) => {
            const key = `refresh:${d.dataset}`;
            const extra = problems(d);
            return (
              <tr key={d.dataset} className="border-b align-top last:border-0" data-freshness={d.freshness}>
                <td className="py-2 pr-3 font-medium">{d.dataset}</td>
                <td className="space-y-1 py-2 pr-3">
                  <FreshnessBadge freshness={d.freshness} />
                  <div className="text-xs"><Lag d={d} /></div>
                  {extra.map((n) => <div key={n} className="text-xs text-destructive">{n}</div>)}
                  {d.schedule_paused && <div className="text-xs text-muted-foreground">Schedule paused</div>}
                </td>
                <td className="py-2 pr-3">
                  {d.covered_to ? <span className="whitespace-nowrap" title={when(d.covered_to)}>{short(d.covered_to)}</span> : <span className="text-muted-foreground">—</span>}
                  {d.last_publish_at && <div className="text-xs whitespace-nowrap text-muted-foreground">published {ago(d.last_publish_at)}</div>}
                </td>
                <td className="py-2 pr-3">
                  {d.last_attempt ? (
                    <span className="inline-flex flex-col gap-1">
                      <RunStatusBadge status={d.last_attempt.status} />
                      <span className="text-xs text-muted-foreground" title={when(d.last_attempt.created_at)}>
                        {d.last_attempt.trigger}, {ago(d.last_attempt.created_at)}
                      </span>
                    </span>
                  ) : <span className="text-muted-foreground">—</span>}
                </td>
                <td className="py-2 text-right">
                  <ConfirmAction
                    label="Refresh now"
                    question={`Sync ${d.dataset} now?`}
                    disabled={!!blocked || !!d.active_run_id}
                    disabledReason={blocked ?? "A run is already queued or running"}
                    pending={action.pendingKey === key}
                    onConfirm={() => action.act(key, () => refreshDataset(connection.id, d.dataset),
                      `Refresh of ${d.dataset} queued. It starts when a worker picks it up.`)}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

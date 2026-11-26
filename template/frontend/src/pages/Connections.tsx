import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";
import { connectionsQuery, operatorHealthQuery } from "@/components/sync/api";
import { ConnectionStateBadge } from "@/components/sync/badges";
import { ago, when } from "@/components/sync/format";
import { OperatorHealthPanel } from "@/components/sync/OperatorHealthPanel";

export function Connections() {
  const connections = useQuery(connectionsQuery);
  const health = useQuery(operatorHealthQuery);
  if (connections.isPending) return <PageSkeleton />;
  if (connections.error) return <ErrorState error={connections.error as ApiError} />;
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">Connections</h1>
      {connections.data.length === 0 ? (
        <div className="space-y-1 text-sm">
          <p>No connections yet</p>
          <p className="text-muted-foreground">Once an account is connected, its datasets and sync runs show here.</p>
        </div>
      ) : (
        <>
          {health.data && <OperatorHealthPanel health={health.data} />}
          {health.error && <ErrorState error={health.error as ApiError} />}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b">
                  <th className="py-2 pr-3 font-medium">Connection</th>
                  <th className="py-2 pr-3 font-medium">State</th>
                  <th className="py-2 pr-3 font-medium">Datasets</th>
                  <th className="py-2 font-medium">Last published</th>
                </tr>
              </thead>
              <tbody>
                {connections.data.map((c) => (
                  <tr key={c.id} className="border-b align-top last:border-0">
                    <td className="py-2 pr-3">
                      <Link to={`/connections/${c.id}`} className="font-medium text-primary hover:underline">{c.display_name}</Link>
                      <div className="text-xs text-muted-foreground">{c.provider} · {c.account_ref}</div>
                    </td>
                    <td className="py-2 pr-3">
                      <ConnectionStateBadge state={c.state} />
                      {c.state_reason && <div className="text-xs text-muted-foreground">{c.state_reason}</div>}
                    </td>
                    <td className="py-2 pr-3">
                      {c.datasets} {c.datasets === 1 ? "dataset" : "datasets"}
                      {c.stale_datasets > 0 && <div className="text-xs text-destructive">{c.stale_datasets} stale</div>}
                      {c.failed_runs_awaiting_action > 0 && (
                        <div className="text-xs text-destructive">
                          {c.failed_runs_awaiting_action} failed {c.failed_runs_awaiting_action === 1 ? "run" : "runs"} to look at
                        </div>
                      )}
                    </td>
                    <td className="py-2">
                      {c.last_publish_at ? <span title={when(c.last_publish_at)}>{ago(c.last_publish_at)}</span> : <span className="text-muted-foreground">Never</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

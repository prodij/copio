import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";
import { Skeleton } from "@/components/ui/skeleton";
import { connectionHealthQuery, runsQuery } from "@/components/sync/api";
import { ConnectionStateBadge } from "@/components/sync/badges";
import { DatasetHealthTable } from "@/components/sync/DatasetHealthTable";
import { RunsTable } from "@/components/sync/RunsTable";
import { ActionNotice, useSyncAction } from "@/components/sync/useSyncAction";

const STATUSES = ["failed", "waiting", "queued", "running", "succeeded", "cancelled"];

export function ConnectionDetail() {
  const { connectionId = "" } = useParams();
  const [status, setStatus] = useState("");
  const health = useQuery(connectionHealthQuery(connectionId));
  const runs = useQuery(runsQuery(connectionId, status ? { status } : {}));
  const action = useSyncAction();

  if (health.isPending) return <PageSkeleton />;
  if (health.error) {
    return (
      <div className="space-y-3">
        <ErrorState error={health.error as ApiError} />
        <Link to="/connections" className="text-sm text-primary underline">All connections</Link>
      </div>
    );
  }
  const { connection, datasets } = health.data;
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <Link to="/connections" className="text-xs text-muted-foreground hover:underline">← Connections</Link>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold">{connection.display_name}</h1>
          <ConnectionStateBadge state={connection.state} />
        </div>
        <p className="text-xs text-muted-foreground">
          {connection.provider} · {connection.account_ref}
          {connection.state_reason ? ` · ${connection.state_reason}` : ""}
        </p>
      </header>

      <section aria-labelledby="datasets" className="space-y-2">
        <h2 id="datasets" className="font-medium">Datasets</h2>
        <p className="text-xs text-muted-foreground">Freshness comes from what has been published completely, not from the latest run.</p>
        <ActionNotice notice={action.notice} scope={["refresh"]} />
        <DatasetHealthTable connection={connection} datasets={datasets} action={action} />
      </section>

      <section aria-labelledby="runs" className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h2 id="runs" className="font-medium">Runs</h2>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Status
            <select value={status} onChange={(e) => setStatus(e.target.value)}
              className="h-7 rounded-md border border-input bg-background px-2 text-xs text-foreground">
              <option value="">All</option>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>
        <ActionNotice notice={action.notice} scope={["retry", "resume", "replay"]} />
        {runs.isPending ? <Skeleton className="h-24 w-full" />
          : runs.error ? <ErrorState error={runs.error as ApiError} />
            : <RunsTable runs={runs.data} connection={connection} action={action} />}
      </section>
    </div>
  );
}

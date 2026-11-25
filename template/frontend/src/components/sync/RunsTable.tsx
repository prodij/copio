import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { type ConnectionSummary, type Run, replayRun, resumeRun, retryRun, runDetailQuery } from "./api";
import { RunStatusBadge } from "./badges";
import { ConfirmAction } from "./ConfirmAction";
import { ago, label, when } from "./format";
import type { useSyncAction } from "./useSyncAction";

const ACTIVE = ["queued", "running", "waiting"];

function RunDetailPanel({ runId }: { runId: string }) {
  const { data, error, isPending } = useQuery(runDetailQuery(runId));
  if (isPending) return <Skeleton className="h-16 w-full" />;
  if (error) return <ErrorState error={error as ApiError} />;
  const rows: [string, string | null][] = [
    ["Window", `${when(data.window_start)} – ${when(data.window_end)}`],
    ["Stage", label(data.stage)],
    ["Attempts", `${data.attempt} of ${data.max_attempts}`],
    ["Records", `${data.records_accepted} accepted, ${data.records_rejected} rejected, ${data.records_stale} older than published`],
    ["Raw pages", `${data.raw_objects} stored, ${data.raw_unprocessed} not yet published`],
    ["Connector version", data.connector_version],
    ["Error", data.error_code ? `${data.error_code}${data.error_detail ? `: ${data.error_detail}` : ""}` : null],
    ["Provider request", data.provider_request_ref],
    ["Waiting for", data.wait_reason ? `${data.wait_reason}${data.next_attempt_at ? ` (next try ${when(data.next_attempt_at)})` : ""}` : null],
    ["Replay of", data.replay_of],
    ["Requested by", data.requested_by],
    ["Run id", data.id],
  ];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1 text-xs">
      {rows.filter(([, v]) => v).map(([k, v]) => (
        <Fragment key={k}>
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="break-all">{v}</dd>
        </Fragment>
      ))}
    </dl>
  );
}

function RunActions({ run, connection, action }: { run: Run; connection: ConnectionSummary; action: ReturnType<typeof useSyncAction> }) {
  const healthy = connection.state === "healthy";
  const blocked = `The connection is ${connection.state.replaceAll("_", " ")}`;
  if (run.status === "failed") {
    return (
      <span className="inline-flex flex-wrap justify-end gap-1.5">
        <ConfirmAction label="Retry" question="Retry this run?" disabled={!healthy} disabledReason={blocked}
          pending={action.pendingKey === `retry:${run.id}`}
          onConfirm={() => action.act(`retry:${run.id}`, () => retryRun(run.id), "Retry queued.")} />
        <ReplayButton run={run} connection={connection} action={action} />
      </span>
    );
  }
  if (run.status === "waiting") {
    return (
      <ConfirmAction label="Resume now" question="Run it now instead of waiting?" disabled={!healthy} disabledReason={blocked}
        pending={action.pendingKey === `resume:${run.id}`}
        onConfirm={() => action.act(`resume:${run.id}`, () => resumeRun(run.id), "Run put back in the queue.")} />
    );
  }
  if (ACTIVE.includes(run.status)) return null;
  return <ReplayButton run={run} connection={connection} action={action} />;
}

function ReplayButton({ run, connection, action }: { run: Run; connection: ConnectionSummary; action: ReturnType<typeof useSyncAction> }) {
  return (
    <ConfirmAction label="Replay" question="Re-publish this run's stored data?"
      disabled={connection.state === "disconnected"} disabledReason="The connection is disconnected"
      pending={action.pendingKey === `replay:${run.id}`}
      onConfirm={() => action.act(`replay:${run.id}`, () => replayRun(run.id), "Replay queued. It re-reads stored data and does not call the provider.")} />
  );
}

export function RunsTable({ runs, connection, action }: { runs: Run[]; connection: ConnectionSummary; action: ReturnType<typeof useSyncAction> }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!runs.length) return <p className="text-sm text-muted-foreground">No runs match.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th className="py-2 pr-3 font-medium">Created</th>
            <th className="py-2 pr-3 font-medium">Dataset</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 pr-3 font-medium">Records</th>
            <th className="py-2 font-medium"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <Fragment key={run.id}>
              <tr className="border-b align-top" data-status={run.status}>
                <td className="py-2 pr-3 whitespace-nowrap" title={when(run.created_at)}>
                  {ago(run.created_at)}
                  <div className="text-xs text-muted-foreground">{run.kind}, {run.trigger}</div>
                </td>
                <td className="py-2 pr-3">{run.dataset}</td>
                <td className="py-2 pr-3">
                  <RunStatusBadge status={run.status} />
                  <div className="text-xs text-muted-foreground">
                    {label(run.stage)}{run.attempt > 1 ? `, attempt ${run.attempt}` : ""}
                    {run.error_code ? <span className="text-destructive">, {run.error_code}</span> : null}
                  </div>
                </td>
                <td className="py-2 pr-3 tabular-nums">{run.records_accepted.toLocaleString()}</td>
                <td className="py-2">
                  <div className="flex flex-wrap items-start justify-end gap-1.5">
                    <RunActions run={run} connection={connection} action={action} />
                    <Button size="xs" variant="ghost" aria-expanded={open === run.id}
                      onClick={() => setOpen(open === run.id ? null : run.id)}>
                      {open === run.id ? "Hide" : "Details"}
                    </Button>
                  </div>
                </td>
              </tr>
              {open === run.id && (
                <tr className="border-b bg-muted/30">
                  <td colSpan={5} className="p-3"><RunDetailPanel runId={run.id} /></td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

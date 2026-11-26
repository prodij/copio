import { queryOptions } from "@tanstack/react-query";
import { api } from "@/api/client";
import { ApiError, toApiError } from "@/api/errors";
import type { components } from "@/api/schema";

export type ConnectionSummary = components["schemas"]["ConnectionSummary"];
export type ConnectionHealth = components["schemas"]["ConnectionHealth"];
export type DatasetHealth = components["schemas"]["DatasetHealth"];
export type OperatorHealth = components["schemas"]["OperatorHealth"];
export type Run = components["schemas"]["RunOut"];
export type RunDetail = components["schemas"]["RunDetail"];

// Same as the one in src/api/queries.ts (not exported there).
async function unwrap<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let result;
  try {
    result = await p;
  } catch {
    throw new ApiError(0, "Network error");
  }
  const { data, error, response } = result;
  if (error !== undefined || data === undefined) throw toApiError(response, error ?? null);
  return data;
}

// A 4xx won't get better by asking again.
const retry = (failures: number, error: Error) => !((error as ApiError).status >= 400 && (error as ApiError).status < 500) && failures < 3;
// Sync state moves on its own; keep the screens roughly current without hammering the API.
const refetchInterval = 30_000;

export const syncKeys = { all: ["sync"] as const };

export const connectionsQuery = queryOptions({
  queryKey: ["sync", "connections"],
  queryFn: () => unwrap(api.GET("/sync/connections")),
  retry,
  refetchInterval,
});

export const operatorHealthQuery = queryOptions({
  queryKey: ["sync", "health"],
  queryFn: () => unwrap(api.GET("/sync/health")),
  retry,
  refetchInterval,
});

export const connectionHealthQuery = (connectionId: string) =>
  queryOptions({
    queryKey: ["sync", "connections", connectionId, "health"],
    queryFn: () => unwrap(api.GET("/sync/connections/{connection_id}/health", { params: { path: { connection_id: connectionId } } })),
    retry,
    refetchInterval,
  });

export type RunFilters = { status?: string; dataset?: string };

export const runsQuery = (connectionId: string, filters: RunFilters) =>
  queryOptions({
    queryKey: ["sync", "runs", connectionId, filters],
    queryFn: () =>
      unwrap(api.GET("/sync/runs", { params: { query: { connection_id: connectionId, limit: 50, ...filters } } })),
    retry,
    refetchInterval,
  });

export const runDetailQuery = (runId: string) =>
  queryOptions({
    queryKey: ["sync", "run", runId],
    queryFn: () => unwrap(api.GET("/sync/runs/{run_id}", { params: { path: { run_id: runId } } })),
    retry,
  });

export const refreshDataset = (connectionId: string, dataset: string) =>
  unwrap(api.POST("/sync/connections/{connection_id}/datasets/{dataset}/refresh", {
    params: { path: { connection_id: connectionId, dataset } },
  }));
export const retryRun = (runId: string) => unwrap(api.POST("/sync/runs/{run_id}/retry", { params: { path: { run_id: runId } } }));
export const resumeRun = (runId: string) => unwrap(api.POST("/sync/runs/{run_id}/resume", { params: { path: { run_id: runId } } }));
export const replayRun = (runId: string) => unwrap(api.POST("/sync/runs/{run_id}/replay", { params: { path: { run_id: runId } } }));

// Connection controls (owner only; the API says so if not). They return the connection, not a run.
const connectionPath = (connectionId: string) => ({ params: { path: { connection_id: connectionId } } });
export const pauseConnection = (connectionId: string) => unwrap(api.POST("/connections/{connection_id}/pause", connectionPath(connectionId)));
export const resumeConnection = (connectionId: string) => unwrap(api.POST("/connections/{connection_id}/resume", connectionPath(connectionId)));
export const disconnectConnection = (connectionId: string) =>
  unwrap(api.POST("/connections/{connection_id}/disconnect", connectionPath(connectionId)));
export const reconnectConnection = (connectionId: string, accessToken: string) =>
  unwrap(api.POST("/connections/{connection_id}/reconnect", {
    ...connectionPath(connectionId),
    body: { credentials: { access_token: accessToken } },
  }));

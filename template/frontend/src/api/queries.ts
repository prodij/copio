import { queryOptions } from "@tanstack/react-query";
import { api } from "./client";
import { ApiError, toApiError } from "./errors";

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

export const meQuery = queryOptions({ queryKey: ["me"], queryFn: () => unwrap(api.GET("/me")) });
export const accessQuery = queryOptions({ queryKey: ["access"], queryFn: () => unwrap(api.GET("/me/access")) });
export const plansQuery = queryOptions({ queryKey: ["plans"], queryFn: () => unwrap(api.GET("/billing/plans")) });
export const premiumReportQuery = queryOptions({
  queryKey: ["premium-report"],
  queryFn: () => unwrap(api.GET("/demo/premium-report")),
  retry: false,
});

export const createWorkspace = (name: string) => unwrap(api.POST("/workspaces", { body: { name } }));
export const startCheckout = (plan_code: string) => unwrap(api.POST("/billing/checkout", { body: { plan_code } }));

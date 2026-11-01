import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router";
import { accessQuery, meQuery } from "@/api/queries";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";

export function Home() {
  const me = useQuery(meQuery);
  const hasWorkspace = !!me.data?.workspace;
  const access = useQuery({ ...accessQuery, enabled: hasWorkspace });
  if (me.error) return <ErrorState error={me.error as ApiError} />;
  if (me.isPending) return <PageSkeleton />;
  if (!hasWorkspace) return <Navigate to="/workspace/new" replace />;
  if (access.error) return <ErrorState error={access.error as ApiError} />;
  if (access.isPending) return <PageSkeleton />;
  // A pending row without a Lago subscription (nothing paid or started) is no plan yet.
  const hasPlan = !!access.data.plan_code && access.data.state !== null && access.data.state !== "pending";
  return <Navigate to={hasPlan ? "/premium" : "/plans"} replace />;
}

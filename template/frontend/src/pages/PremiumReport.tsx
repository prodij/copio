import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { premiumReportQuery } from "@/api/queries";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";

export function PremiumReport() {
  const { data, error, isPending } = useQuery(premiumReportQuery);
  if (isPending) return <PageSkeleton />;
  if (error) {
    return (
      <div className="space-y-3">
        <ErrorState error={error as ApiError} />
        {(error as ApiError).status === 402 && <Link to="/plans" className="text-primary underline">See plans</Link>}
      </div>
    );
  }
  return (
    <article className="space-y-2">
      <h1 className="text-lg font-semibold">{data.title}</h1>
      <p className="text-sm text-muted-foreground">Generated for {data.generated_for}</p>
    </article>
  );
}

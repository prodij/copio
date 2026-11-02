import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { accessQuery } from "@/api/queries";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";
import { Unavailable } from "@/components/Unavailable";

export function Billing() {
  const { data, error, isPending } = useQuery(accessQuery);
  if (isPending) return <PageSkeleton />;
  if (error) return <ErrorState error={error as ApiError} />;
  if (!data.plan_code) {
    return (
      <div className="space-y-2">
        {data.billing_configured ? (
          <p>No plan yet</p>
        ) : (
          <>
            <p>Billing isn&apos;t set up</p>
            <p className="text-sm text-muted-foreground">
              Plans can&apos;t be bought until a Stripe test key is added: put it in STRIPE_SECRET_KEY in .env and run make bootstrap.
            </p>
          </>
        )}
        <Link to="/plans" className="text-primary underline">See plans</Link>
      </div>
    );
  }
  const features = Object.entries(data.features);
  return (
    <dl className="grid max-w-md grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
      <dt className="text-muted-foreground">Plan</dt><dd>{data.plan_code}</dd>
      <dt className="text-muted-foreground">State</dt><dd>{data.state ?? <Unavailable />}</dd>
      <dt className="text-muted-foreground">Current period ends</dt>
      <dd>{data.current_period_end ? new Date(data.current_period_end).toLocaleDateString() : <Unavailable />}</dd>
      <dt className="text-muted-foreground">Features</dt>
      <dd>{features.length ? features.map(([k, v]) => (v === true ? k : `${k}: ${String(v)}`)).join(", ") : "None granted yet"}</dd>
    </dl>
  );
}

import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import { accessQuery } from "@/api/queries";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";
import { Button } from "@/components/ui/button";

// Stands where Stripe's hosted page stands in the real flow, and like it leads to /billing/return.
// Confirming changes nothing here: the return page creates the Lago subscription and access follows
// Lago's webhook. Only the server's BILLING_MODE decides whether this page does anything.
export function MockPayment() {
  const navigate = useNavigate();
  const { data, error, isPending } = useQuery(accessQuery);
  if (isPending) return <PageSkeleton />;
  if (error) return <ErrorState error={error as ApiError} />;
  if (!data.mock_payment) {
    return (
      <div className="space-y-2">
        <p>Mock payment is off.</p>
        <Link to="/plans" className="text-primary underline">See plans</Link>
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <h1 className="text-lg font-semibold">Mock payment</h1>
      <p className="text-sm text-muted-foreground">
        No card and no money. Your plan turns on only when Lago&apos;s webhook reaches the backend.
      </p>
      <Button onClick={() => void navigate("/billing/return")}>Confirm mock payment</Button>
    </div>
  );
}

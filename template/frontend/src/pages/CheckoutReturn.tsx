import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { accessQuery, startCheckout } from "@/api/queries";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PLAN_KEY } from "./Plans";

const POLL_MS = 2_000;
const GIVE_UP_MS = 60_000;

function readPlan(): string | null {
  try {
    return window.sessionStorage.getItem(PLAN_KEY);
  } catch {
    return null;
  }
}

// Option A: coming back from Stripe only means a card was saved. A second checkout call creates
// the payment-gated subscription; access switches on only when /me/access says "active".
export function CheckoutReturn() {
  const [startedAt] = useState(() => Date.now());
  const [plan] = useState(readPlan);
  const [timedOut, setTimedOut] = useState(false);
  const second = useMutation({ mutationFn: startCheckout });
  const { mutate } = second;
  const redirectUrl = second.data?.checkout_url;

  useEffect(() => {
    if (plan !== null) mutate(plan);
  }, [plan, mutate]);

  useEffect(() => {
    if (redirectUrl) window.location.assign(redirectUrl);
  }, [redirectUrl]);

  useEffect(() => {
    const t = setTimeout(() => setTimedOut(true), GIVE_UP_MS);
    return () => clearTimeout(t);
  }, []);

  const { data, error } = useQuery({
    ...accessQuery,
    enabled: plan === null || second.isSuccess,
    refetchInterval: (q) =>
      q.state.data?.state === "active" || Date.now() - startedAt > GIVE_UP_MS ? false : POLL_MS,
  });

  if (second.error) return <ErrorState error={second.error as ApiError} />;
  if (error) return <ErrorState error={error as ApiError} />;
  if (data?.state === "active") {
    return (
      <div className="space-y-2">
        <p>Your plan is active.</p>
        <Link to="/premium" className="text-primary underline">Open premium report</Link>
      </div>
    );
  }
  if (timedOut) {
    return <p className="text-sm text-muted-foreground">Payment is not confirmed yet. Reload this page in a moment.</p>;
  }
  return <p className="text-sm text-muted-foreground">Waiting for payment confirmation…</p>;
}

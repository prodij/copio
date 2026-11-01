import { useQuery, useQueryClient } from "@tanstack/react-query";
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
  const queryClient = useQueryClient();
  // A query (not an effect-fired mutation) so StrictMode's double mount shares one request.
  const second = useQuery({
    queryKey: ["checkout-second-leg", plan],
    enabled: plan !== null,
    retry: false,
    staleTime: Infinity,
    gcTime: Infinity,
    queryFn: async () => {
      const out = await startCheckout(plan as string);
      // Any cached /me/access predates this call; drop it so a stale "active" is never shown.
      queryClient.removeQueries({ queryKey: accessQuery.queryKey });
      return out;
    },
  });
  const redirectUrl = second.data?.checkout_url;

  useEffect(() => {
    if (!second.isSuccess) return;
    try {
      window.sessionStorage.removeItem(PLAN_KEY);
    } catch {
      /* storage blocked */
    }
  }, [second.isSuccess]);

  useEffect(() => {
    if (redirectUrl) window.location.assign(redirectUrl);
  }, [redirectUrl]);

  useEffect(() => {
    const t = setTimeout(() => setTimedOut(true), GIVE_UP_MS);
    return () => clearTimeout(t);
  }, []);

  const secondDone = plan === null || second.isSuccess;
  const { data, error } = useQuery({
    ...accessQuery,
    enabled: secondDone,
    refetchInterval: (q) =>
      q.state.data?.state === "active" || Date.now() - startedAt > GIVE_UP_MS ? false : POLL_MS,
  });

  if (second.error) return <ErrorState error={second.error as ApiError} />;
  if (error) return <ErrorState error={error as ApiError} />;
  if (secondDone && data?.state === "active") {
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

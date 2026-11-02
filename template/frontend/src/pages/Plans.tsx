import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { accessQuery, plansQuery, startCheckout } from "@/api/queries";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const PLAN_KEY = "checkout_plan";
// A 503 right after sign-up is usually Lago still creating the Stripe customer (a background job
// that takes a few seconds): retry 3 times, 1 s, 2 s and 4 s apart, before showing the error.
export const CHECKOUT_RETRIES = 3;
const checkoutRetryDelay = (attempt: number) => 1000 * 2 ** attempt;

// Remembered so CheckoutReturn can make the checkout call that follows the payment page.
function rememberPlan(code: string) {
  try {
    window.sessionStorage.setItem(PLAN_KEY, code);
  } catch {
    /* storage blocked: the return page then only polls */
  }
}

const money = (cents: number, currency: string) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);

export function Plans() {
  const navigate = useNavigate();
  const plans = useQuery(plansQuery);
  const access = useQuery({ ...accessQuery, retry: false });
  const choose = (code: string) => {
    if (!access.data?.mock_payment) return checkout.mutate(code);
    rememberPlan(code);
    void navigate("/billing/mock-payment");
  };
  const checkout = useMutation({
    retry: (failures, error) => (error as ApiError).status === 503 && failures < CHECKOUT_RETRIES,
    retryDelay: checkoutRetryDelay,
    mutationFn: async (code: string) => {
      const out = await startCheckout(code);
      rememberPlan(code);
      return out;
    },
    onSuccess: ({ checkout_url }) => {
      if (checkout_url) window.location.assign(checkout_url);
      else void navigate("/billing/return");
    },
  });
  if (plans.isPending || access.isPending) return <PageSkeleton />;
  if (plans.error) return <ErrorState error={plans.error as ApiError} />;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {checkout.error && <ErrorState error={checkout.error as ApiError} />}
      {plans.data.map((p) => (
        <Card key={p.code}>
          <CardHeader><CardTitle>{p.name}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">{money(p.amount_cents, p.currency)} / {p.interval}</p>
            <Button disabled={checkout.isPending} onClick={() => choose(p.code)}>Choose {p.name}</Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

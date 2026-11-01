import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { plansQuery, startCheckout } from "@/api/queries";
import type { ApiError } from "@/api/errors";
import { ErrorState } from "@/components/ErrorState";
import { PageSkeleton } from "@/components/PageSkeleton";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const PLAN_KEY = "checkout_plan";

const money = (cents: number, currency: string) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);

export function Plans() {
  const navigate = useNavigate();
  const plans = useQuery(plansQuery);
  const checkout = useMutation({
    mutationFn: async (code: string) => {
      const out = await startCheckout(code);
      // Remembered so CheckoutReturn can make the second checkout call after Stripe.
      try {
        window.sessionStorage.setItem(PLAN_KEY, code);
      } catch {
        /* storage blocked: the return page then only polls */
      }
      return out;
    },
    onSuccess: ({ checkout_url }) => {
      if (checkout_url) window.location.assign(checkout_url);
      else void navigate("/billing/return");
    },
  });
  if (plans.isPending) return <PageSkeleton />;
  if (plans.error) return <ErrorState error={plans.error as ApiError} />;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {checkout.error && <ErrorState error={checkout.error as ApiError} />}
      {plans.data.map((p) => (
        <Card key={p.code}>
          <CardHeader><CardTitle>{p.name}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">{money(p.amount_cents, p.currency)} / {p.interval}</p>
            <Button disabled={checkout.isPending} onClick={() => checkout.mutate(p.code)}>Choose {p.name}</Button>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

import { useQuery } from "@tanstack/react-query";
import { accessQuery } from "@/api/queries";

// So nobody mistakes mock payment for real billing. Before a workspace exists /me/access answers 403:
// no banner then, and accessQuery doesn't retry it.
export function MockPaymentBanner() {
  const { data } = useQuery(accessQuery);
  if (!data?.mock_payment) return null;
  return (
    <p role="status" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm font-medium">
      Mock payment: this is not real billing. Nothing is charged and Stripe is never called.
    </p>
  );
}

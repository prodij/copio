import { act, fireEvent, screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { Plans } from "./Plans";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const plan = { code: "starter", name: "Starter", amount_cents: 2900, currency: "USD", interval: "month", features: { premium_report: true } };

it("lists plans and starts checkout", async () => {
  const assign = vi.fn();
  vi.stubGlobal("location", { ...window.location, assign });
  mockFetch({
    "GET /billing/plans": { status: 200, body: [plan] },
    "POST /billing/checkout": { status: 200, body: { checkout_url: "https://checkout.stripe.test/s" } },
  });
  renderWithQuery(<Plans />);
  expect(await screen.findByText("$29.00 / month")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Choose Starter" }));
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.test/s"));
});

it("goes to the return page when no redirect is needed", async () => {
  mockFetch({
    "GET /billing/plans": { status: 200, body: [plan] },
    "POST /billing/checkout": { status: 200, body: { checkout_url: null } },
  });
  renderWithQuery(
    <Routes>
      <Route path="/" element={<Plans />} />
      <Route path="/billing/return" element={<p>return page</p>} />
    </Routes>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  expect(await screen.findByText("return page")).toBeInTheDocument();
  expect(window.sessionStorage.getItem("checkout_plan")).toBe("starter");
});

const checkoutCalls = (spy: ReturnType<typeof mockFetch>) =>
  spy.mock.calls.filter(([input]) => (input as Request).method === "POST").length;

it("shows the API error when checkout is rejected, without retrying", async () => {
  const spy = mockFetch({
    "GET /billing/plans": { status: 200, body: [{ ...plan, features: {} }] },
    "POST /billing/checkout": { status: 502, body: { detail: "Lago rejected the request: validation_errors" } },
  });
  renderWithQuery(<Plans />);
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  expect(await screen.findByText("Lago rejected the request: validation_errors")).toBeInTheDocument();
  expect(checkoutCalls(spy)).toBe(1);
});

it("shows that billing isn't set up, without retrying", async () => {
  const detail = "Billing isn't set up: this product has no Stripe key.";
  const spy = mockFetch({
    "GET /billing/plans": { status: 200, body: [plan] },
    "POST /billing/checkout": { status: 501, body: { detail } },
  });
  window.sessionStorage.removeItem("checkout_plan");
  renderWithQuery(<Plans />);
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  expect(await screen.findByText(detail)).toBeInTheDocument();
  expect(checkoutCalls(spy)).toBe(1);
  expect(window.sessionStorage.getItem("checkout_plan")).toBeNull();
});

it("retries a 503 a few times before showing it", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const spy = mockFetch({
    "GET /billing/plans": { status: 200, body: [plan] },
    "POST /billing/checkout": { status: 503, body: { detail: "Stripe customer is unavailable" } },
  });
  renderWithQuery(<Plans />);
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  await act(() => vi.advanceTimersByTimeAsync(2_500));
  expect(screen.queryByText("Stripe customer is unavailable")).not.toBeInTheDocument();
  await act(() => vi.advanceTimersByTimeAsync(5_000));
  expect(await screen.findByText("Stripe customer is unavailable")).toBeInTheDocument();
  expect(checkoutCalls(spy)).toBe(4);
});

it("goes on once the Stripe customer exists", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const assign = vi.fn();
  vi.stubGlobal("location", { ...window.location, assign });
  let calls = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: Request) => {
    if (input.method === "GET") return Response.json([plan]);
    calls += 1;
    return calls < 3
      ? Response.json({ detail: "Stripe customer is unavailable" }, { status: 503 })
      : Response.json({ checkout_url: "https://checkout.stripe.test/s" });
  }));
  renderWithQuery(<Plans />);
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  await act(() => vi.advanceTimersByTimeAsync(4_000));
  await vi.waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.test/s"));
  expect(calls).toBe(3);
  expect(screen.queryByText("Stripe customer is unavailable")).not.toBeInTheDocument();
});

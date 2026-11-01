import { act, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { CheckoutReturn } from "./CheckoutReturn";

beforeEach(() => window.sessionStorage.clear());
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("waits while pending", async () => {
  mockFetch({ "GET /me/access": { status: 200, body: { plan_code: "starter", state: "pending", features: {} } } });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByText("Waiting for payment confirmation…")).toBeInTheDocument();
});

it("confirms when active", async () => {
  mockFetch({ "GET /me/access": { status: 200, body: { plan_code: "starter", state: "active", features: { premium_report: true } } } });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByRole("link", { name: "Open premium report" })).toBeInTheDocument();
});

it("makes the second checkout call with the remembered plan before polling", async () => {
  window.sessionStorage.setItem("checkout_plan", "starter");
  const spy = mockFetch({
    "POST /billing/checkout": { status: 200, body: { checkout_url: null } },
    "GET /me/access": { status: 200, body: { plan_code: "starter", state: "pending", features: {} } },
  });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByText("Waiting for payment confirmation…")).toBeInTheDocument();
  await vi.waitFor(() => expect(calls(spy)).toContain("GET /me/access"));
  expect(calls(spy)[0]).toBe("POST /billing/checkout");
});

it("shows the API error when the second call fails", async () => {
  window.sessionStorage.setItem("checkout_plan", "starter");
  mockFetch({ "POST /billing/checkout": { status: 502, body: { detail: "card declined" } } });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByText("card declined")).toBeInTheDocument();
});

const calls = (spy: ReturnType<typeof mockFetch>) =>
  spy.mock.calls.map(([r]) => `${(r as Request).method} ${new URL((r as Request).url).pathname}`);

it("posts checkout exactly once under StrictMode and clears the remembered plan", async () => {
  window.sessionStorage.setItem("checkout_plan", "starter");
  const spy = mockFetch({
    "POST /billing/checkout": { status: 200, body: { checkout_url: null } },
    "GET /me/access": { status: 200, body: { plan_code: "starter", state: "pending", features: {} } },
  });
  renderWithQuery(<StrictMode><CheckoutReturn /></StrictMode>);
  expect(await screen.findByText("Waiting for payment confirmation…")).toBeInTheDocument();
  expect(calls(spy).filter((c) => c === "POST /billing/checkout")).toHaveLength(1);
  await vi.waitFor(() => expect(window.sessionStorage.getItem("checkout_plan")).toBeNull());
});

it("stops polling after 60 s and says payment is not confirmed", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const spy = mockFetch({ "GET /me/access": { status: 200, body: { plan_code: "starter", state: "pending", features: {} } } });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByText("Waiting for payment confirmation…")).toBeInTheDocument();
  await act(() => vi.advanceTimersByTimeAsync(62_000));
  expect(screen.getByText(/not confirmed yet/)).toBeInTheDocument();
  const n = calls(spy).length;
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  expect(calls(spy)).toHaveLength(n);
});

it("retries the second call while Lago has not seen the card yet, then polls access", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  window.sessionStorage.setItem("checkout_plan", "starter");
  const assign = vi.fn();
  vi.stubGlobal("location", { ...window.location, assign });
  let answers = 0;
  const spy = mockFetch({
    "GET /me/access": { status: 200, body: { plan_code: "starter", state: "active", features: { premium_report: true } } },
  });
  const pending = spy.getMockImplementation()!;
  spy.mockImplementation(async (input, init) => {
    const req = input instanceof Request ? input : new Request(input, init);
    if (req.method === "POST") {
      answers += 1;
      const body = { checkout_url: answers < 3 ? "https://checkout.stripe.test/s" : null };
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return pending(input, init);
  });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByText("Waiting for payment confirmation…")).toBeInTheDocument();
  expect(calls(spy)).not.toContain("GET /me/access");
  await act(() => vi.advanceTimersByTimeAsync(4_500));
  expect(await screen.findByRole("link", { name: "Open premium report" })).toBeInTheDocument();
  expect(calls(spy).filter((c) => c === "POST /billing/checkout")).toHaveLength(3);
  expect(assign).not.toHaveBeenCalled();
  expect(window.sessionStorage.getItem("checkout_plan")).toBeNull();
});

it("after the cap says it is still confirming and never goes back to Stripe", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  window.sessionStorage.setItem("checkout_plan", "starter");
  const assign = vi.fn();
  vi.stubGlobal("location", { ...window.location, assign });
  const spy = mockFetch({ "POST /billing/checkout": { status: 200, body: { checkout_url: "https://checkout.stripe.test/s" } } });
  renderWithQuery(<CheckoutReturn />);
  await act(() => vi.advanceTimersByTimeAsync(62_000));
  expect(screen.getByText(/still confirming it — we.ll finish this shortly/)).toBeInTheDocument();
  const n = calls(spy).length;
  expect(n).toBeGreaterThan(20);
  await act(() => vi.advanceTimersByTimeAsync(10_000));
  expect(calls(spy)).toHaveLength(n);
  expect(calls(spy)).not.toContain("GET /me/access");
  expect(assign).not.toHaveBeenCalled();
});

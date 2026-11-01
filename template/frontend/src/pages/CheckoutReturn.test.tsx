import { screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { CheckoutReturn } from "./CheckoutReturn";

beforeEach(() => window.sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

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
  const calls = spy.mock.calls.map(([r]) => `${(r as Request).method} ${new URL((r as Request).url).pathname}`);
  expect(calls[0]).toBe("POST /billing/checkout");
  expect(calls).toContain("GET /me/access");
});

it("shows the API error when the second call fails", async () => {
  window.sessionStorage.setItem("checkout_plan", "starter");
  mockFetch({ "POST /billing/checkout": { status: 502, body: { detail: "card declined" } } });
  renderWithQuery(<CheckoutReturn />);
  expect(await screen.findByText("card declined")).toBeInTheDocument();
});

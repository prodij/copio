import { fireEvent, screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { MockPayment } from "./MockPayment";

beforeEach(() => window.sessionStorage.setItem("checkout_plan", "starter"));
afterEach(() => {
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
});

const access = (mock_payment: boolean) => ({
  "GET /me/access": { status: 200, body: { billing_configured: true, mock_payment, plan_code: null, state: null, features: {}, current_period_end: null } },
});

it("goes to the return page and asks the API for nothing else", async () => {
  const spy = mockFetch(access(true));
  renderWithQuery(
    <Routes>
      <Route path="/" element={<MockPayment />} />
      <Route path="/billing/return" element={<p>return page</p>} />
    </Routes>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Confirm mock payment" }));
  expect(await screen.findByText("return page")).toBeInTheDocument();
  expect(spy.mock.calls.filter(([input]) => (input as Request).method !== "GET")).toEqual([]);
});

it("does nothing with real billing", async () => {
  mockFetch(access(false));
  renderWithQuery(<MockPayment />);
  expect(await screen.findByText("Mock payment is off.")).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("links to the plans page when no plan was chosen", async () => {
  window.sessionStorage.clear();
  mockFetch(access(true));
  renderWithQuery(<MockPayment />);
  expect(await screen.findByRole("link", { name: "See plans" })).toHaveAttribute("href", "/plans");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

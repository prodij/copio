import { screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { MockPaymentBanner } from "./MockPaymentBanner";

afterEach(() => vi.unstubAllGlobals());

const access = (mock_payment: boolean) => ({
  "GET /me/access": { status: 200, body: { billing_configured: true, mock_payment, plan_code: null, state: null, features: {}, current_period_end: null } },
});

it("says it is a mock payment, not real billing", async () => {
  mockFetch(access(true));
  renderWithQuery(<MockPaymentBanner />);
  expect(await screen.findByRole("status")).toHaveTextContent("Mock payment: this is not real billing");
});

it("stays away with real billing", async () => {
  const spy = mockFetch(access(false));
  renderWithQuery(<MockPaymentBanner />);
  await vi.waitFor(() => expect(spy).toHaveBeenCalled());
  await new Promise((r) => setTimeout(r));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("stays away before a workspace exists", async () => {
  const spy = mockFetch({ "GET /me/access": { status: 403, body: { detail: "no workspace" } } });
  renderWithQuery(<MockPaymentBanner />);
  await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

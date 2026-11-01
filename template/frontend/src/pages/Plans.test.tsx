import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { Plans } from "./Plans";

afterEach(() => vi.unstubAllGlobals());

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
  renderWithQuery(<Plans />);
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  await vi.waitFor(() => expect(window.sessionStorage.getItem("checkout_plan")).toBe("starter"));
});

it("shows the API error when checkout fails", async () => {
  mockFetch({
    "GET /billing/plans": { status: 200, body: [{ ...plan, features: {} }] },
    "POST /billing/checkout": { status: 503, body: { detail: "Lago is unavailable" } },
  });
  renderWithQuery(<Plans />);
  fireEvent.click(await screen.findByRole("button", { name: "Choose Starter" }));
  expect(await screen.findByText("Lago is unavailable")).toBeInTheDocument();
});

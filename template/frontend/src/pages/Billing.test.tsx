import { screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { Billing } from "./Billing";

afterEach(() => vi.unstubAllGlobals());

it("shows no plan yet", async () => {
  mockFetch({ "GET /me/access": { status: 200, body: { plan_code: null, state: null, features: {}, current_period_end: null } } });
  renderWithQuery(<Billing />);
  expect(await screen.findByText("No plan yet")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See plans" })).toHaveAttribute("href", "/plans");
});

it("shows Unavailable for a missing period end, not zero", async () => {
  mockFetch({ "GET /me/access": { status: 200, body: { plan_code: "starter", state: "pending", features: {}, current_period_end: null } } });
  renderWithQuery(<Billing />);
  expect(await screen.findByText("starter")).toBeInTheDocument();
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
});

it("shows status and message on failure", async () => {
  mockFetch({ "GET /me/access": { status: 503, body: { detail: "db is unavailable" } } });
  renderWithQuery(<Billing />);
  expect(await screen.findByText("db is unavailable")).toBeInTheDocument();
  expect(screen.getByText("503")).toBeInTheDocument();
});

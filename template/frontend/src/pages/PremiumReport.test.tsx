import { screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { PremiumReport } from "./PremiumReport";

afterEach(() => vi.unstubAllGlobals());

it("shows the report when allowed", async () => {
  mockFetch({ "GET /demo/premium-report": { status: 200, body: { title: "Premium report", generated_for: "Acme" } } });
  renderWithQuery(<PremiumReport />);
  expect(await screen.findByText("Premium report")).toBeInTheDocument();
  expect(screen.getByText(/Acme/)).toBeInTheDocument();
});

it("shows the upgrade path on 402", async () => {
  mockFetch({ "GET /demo/premium-report": { status: 402, body: { detail: "no subscription" } } });
  renderWithQuery(<PremiumReport />);
  expect(await screen.findByText("no subscription")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "See plans" })).toHaveAttribute("href", "/plans");
});

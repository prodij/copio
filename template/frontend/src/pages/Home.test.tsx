import { Route, Routes } from "react-router";
import { screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { Home } from "./Home";

afterEach(() => vi.unstubAllGlobals());

const me = (workspace: unknown) => ({ status: 200, body: { user_id: "u", email: null, workspace } });
const ws = { id: "w", name: "Acme", role: "owner" };

function renderHome() {
  renderWithQuery(
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/workspace/new" element={<p>new workspace</p>} />
      <Route path="/plans" element={<p>plans page</p>} />
      <Route path="/premium" element={<p>premium page</p>} />
    </Routes>,
  );
}

it("sends a user without a workspace to create one", async () => {
  mockFetch({ "GET /me": me(null) });
  renderHome();
  expect(await screen.findByText("new workspace")).toBeInTheDocument();
});

it("sends a workspace without a plan to plans", async () => {
  mockFetch({ "GET /me": me(ws), "GET /me/access": { status: 200, body: { plan_code: null, state: null, features: {}, current_period_end: null } } });
  renderHome();
  expect(await screen.findByText("plans page")).toBeInTheDocument();
});

it("treats a pending plan as no plan", async () => {
  mockFetch({ "GET /me": me(ws), "GET /me/access": { status: 200, body: { plan_code: "starter", state: "pending", features: {}, current_period_end: null } } });
  renderHome();
  expect(await screen.findByText("plans page")).toBeInTheDocument();
});

it("sends an active plan to the premium page", async () => {
  mockFetch({ "GET /me": me(ws), "GET /me/access": { status: 200, body: { plan_code: "starter", state: "active", features: { premium_report: true }, current_period_end: null } } });
  renderHome();
  expect(await screen.findByText("premium page")).toBeInTheDocument();
});

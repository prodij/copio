import { screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { Connections } from "./Connections";

afterEach(() => vi.unstubAllGlobals());

const quiet = {
  checked_at: "2026-11-25T12:00:00Z", recent_window_s: 86400, queued_runs: 0, outbox_pending: 0,
  oldest_queued_age_s: null, oldest_unpublished: null, oldest_unprocessed_raw_at: null, rate_limited_recent: 0,
  waiting_runs: 0, expired_leases: 0, reconnect_needed_connections: 0, auth_failures_recent: 0,
  failed_runs_awaiting_action: 0,
};

const conn = (over: object) => ({
  id: "c1", provider: "synthetic", account_ref: "acct-1", display_name: "Demo shop", state: "healthy",
  state_reason: null, datasets: 2, stale_datasets: 0, failed_runs_awaiting_action: 0,
  last_publish_at: new Date(Date.now() - 5 * 60_000).toISOString(), ...over,
});

it("lists connections with their state, stale datasets and what needs attention", async () => {
  mockFetch({
    "GET /sync/connections": { status: 200, body: [
      conn({}),
      conn({ id: "c2", display_name: "Revoked shop", state: "reconnect_needed", state_reason: "token revoked",
        stale_datasets: 1, failed_runs_awaiting_action: 2, last_publish_at: null }),
    ] },
    "GET /sync/health": { status: 200, body: { ...quiet, failed_runs_awaiting_action: 2, reconnect_needed_connections: 1 } },
  });
  renderWithQuery(<Connections />);

  const revoked = (await screen.findByRole("link", { name: "Revoked shop" })).closest("tr")!;
  expect(revoked).toHaveTextContent("Reconnect needed");
  expect(revoked).toHaveTextContent("token revoked");
  expect(revoked).toHaveTextContent("1 stale");
  expect(revoked).toHaveTextContent("2 datasets");
  expect(revoked).not.toHaveTextContent(", 1 stale");
  expect(revoked).toHaveTextContent("2 failed runs to look at");
  expect(revoked).toHaveTextContent("Never");
  expect(screen.getByRole("link", { name: "Demo shop" })).toHaveAttribute("href", "/connections/c1");

  const attention = await screen.findByRole("region", { name: "Needs attention" });
  expect(within(attention).getByText("2 failed runs need a retry or replay")).toBeInTheDocument();
  expect(within(attention).getByText("1 connection needs reconnecting")).toBeInTheDocument();
});

it("says so when nothing needs attention", async () => {
  mockFetch({
    "GET /sync/connections": { status: 200, body: [conn({})] },
    "GET /sync/health": { status: 200, body: quiet },
  });
  renderWithQuery(<Connections />);
  expect(await screen.findByText("Nothing right now.")).toBeInTheDocument();
});

it("has an empty state", async () => {
  mockFetch({
    "GET /sync/connections": { status: 200, body: [] },
    "GET /sync/health": { status: 200, body: quiet },
  });
  renderWithQuery(<Connections />);
  expect(await screen.findByText("No connections yet")).toBeInTheDocument();
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
});

it("shows the API error", async () => {
  mockFetch({
    "GET /sync/connections": { status: 403, body: { detail: "No workspace for this user" } },
    "GET /sync/health": { status: 403, body: { detail: "No workspace for this user" } },
  });
  renderWithQuery(<Connections />);
  expect(await screen.findByRole("alert")).toHaveTextContent("No workspace for this user");
});

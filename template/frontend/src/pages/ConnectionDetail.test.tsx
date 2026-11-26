import { fireEvent, screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { ConnectionDetail } from "./ConnectionDetail";

afterEach(() => vi.unstubAllGlobals());

const minsAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

const connection = {
  id: "c1", provider: "synthetic", account_ref: "acct-1", display_name: "Demo shop", state: "healthy",
  state_reason: null, datasets: 1, stale_datasets: 1, failed_runs_awaiting_action: 1, last_publish_at: minsAgo(180),
};

const brief = { id: "r-ok", kind: "incremental", trigger: "schedule", status: "succeeded", stage: "published",
  created_at: minsAgo(2), finished_at: minsAgo(1), error_code: null };

const dataset = {
  dataset: "orders", freshness: "stale", freshness_target_s: 3600, lag_s: 3 * 3600, covered_from: minsAgo(9000),
  covered_to: minsAgo(180), last_publish_at: minsAgo(180), last_publish_run_id: "r-old", last_attempt_at: minsAgo(2),
  last_attempt: brief, active_run_id: null, missing_periods: [], replay_backlog: 2, lease_expired: false,
  schedule_paused: false,
};

const run = (over: object) => ({
  id: "r-failed", connection_id: "c1", dataset: "orders", kind: "incremental", trigger: "schedule", status: "failed",
  stage: "fetching", attempt: 5, max_attempts: 5, window_start: minsAgo(120), window_end: minsAgo(60),
  connector_version: "synthetic-1.0", error_code: "http_500", records_accepted: 0, records_rejected: 0,
  records_stale: 0, replay_of: null, next_attempt_at: null, created_at: minsAgo(30), started_at: minsAgo(30),
  finished_at: minsAgo(29), ...over,
});

const health = (over: object = {}) => ({
  "GET /sync/connections/c1/health": { status: 200, body: { connection: { ...connection, ...over }, datasets: [dataset], checked_at: minsAgo(0) } },
});

function renderPage() {
  return renderWithQuery(
    <Routes><Route path="/connections/:connectionId" element={<ConnectionDetail />} /></Routes>,
    "/connections/c1",
  );
}

const posts = (spy: ReturnType<typeof mockFetch>) =>
  spy.mock.calls.map(([input]) => input as Request).filter((r) => r.method === "POST").map((r) => new URL(r.url).pathname);

it("shows a stale dataset as stale even though its last run succeeded", async () => {
  mockFetch({ ...health(), "GET /sync/runs": { status: 200, body: [] } });
  renderPage();
  const row = (await screen.findByText("orders", { selector: "td" })).closest("tr")!;
  expect(within(row).getByText("Stale")).toBeInTheDocument();
  expect(within(row).getByText("Succeeded")).toBeInTheDocument();
  expect(row).toHaveTextContent("3h behind");
  expect(row).toHaveTextContent("2 raw pages saved but not published");
  expect(await screen.findByText("No runs match.")).toBeInTheDocument();
});

it("asks before a refresh, then queues it", async () => {
  const spy = mockFetch({
    ...health(), "GET /sync/runs": { status: 200, body: [] },
    "POST /sync/connections/c1/datasets/orders/refresh": { status: 202, body: run({ id: "r-new", status: "queued", trigger: "manual" }) },
  });
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Refresh now" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(posts(spy)).toEqual([]);

  fireEvent.click(screen.getByRole("button", { name: "Refresh now" }));
  expect(screen.getByText("Sync orders now?")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Refresh of orders queued");
  expect(posts(spy)).toEqual(["/sync/connections/c1/datasets/orders/refresh"]);
});

it("can't refresh a paused connection", async () => {
  mockFetch({ ...health({ state: "paused" }), "GET /sync/runs": { status: 200, body: [] } });
  renderPage();
  expect(await screen.findByRole("button", { name: "Refresh now" })).toBeDisabled();
  expect(screen.getByText("Paused")).toBeInTheDocument();
});

it("retries a failed run and shows a refusal from the API", async () => {
  const spy = mockFetch({
    ...health(), "GET /sync/runs": { status: 200, body: [run({})] },
    "POST /sync/runs/r-failed/retry": { status: 409, body: { detail: "This run was already retried" } },
  });
  renderPage();
  const row = (await screen.findByText("http_500", { exact: false })).closest("tr")!;
  expect(within(row).queryByRole("button", { name: "Resume now" })).not.toBeInTheDocument();
  fireEvent.click(within(row).getByRole("button", { name: "Retry" }));
  fireEvent.click(within(row).getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("This run was already retried");
  expect(posts(spy)).toEqual(["/sync/runs/r-failed/retry"]);
});

it("resumes a waiting run", async () => {
  const spy = mockFetch({
    ...health(), "GET /sync/runs": { status: 200, body: [run({ id: "r-wait", status: "waiting", error_code: null })] },
    "POST /sync/runs/r-wait/resume": { status: 202, body: run({ id: "r-wait", status: "queued" }) },
  });
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Resume now" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Run put back in the queue.");
  expect(posts(spy)).toEqual(["/sync/runs/r-wait/resume"]);
});

it("replays a finished run and shows run details", async () => {
  const spy = mockFetch({
    ...health(), "GET /sync/runs": { status: 200, body: [run({ id: "r-ok", status: "succeeded", error_code: null, records_accepted: 12 })] },
    "GET /sync/runs/r-ok": { status: 200, body: { ...run({ id: "r-ok", status: "succeeded", error_code: null, records_accepted: 12 }),
      error_detail: null, provider_request_ref: "req-9", wait_reason: null, requested_by: null, enqueued_at: minsAgo(30),
      raw_objects: 3, raw_unprocessed: 0 } },
    "POST /sync/runs/r-ok/replay": { status: 202, body: run({ id: "r-replay", kind: "replay", status: "queued" }) },
  });
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Details" }));
  expect(await screen.findByText("req-9")).toBeInTheDocument();
  expect(screen.getByText("3 stored, 0 not yet published")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Replay" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Replay queued");
  expect(posts(spy)).toEqual(["/sync/runs/r-ok/replay"]);
});

it("filters runs by status", async () => {
  const spy = mockFetch({ ...health(), "GET /sync/runs": { status: 200, body: [] } });
  renderPage();
  fireEvent.change(await screen.findByLabelText("Status"), { target: { value: "failed" } });
  await vi.waitFor(() => {
    const urls = spy.mock.calls.map(([input]) => new URL((input as Request).url));
    expect(urls.some((u) => u.pathname === "/sync/runs" && u.searchParams.get("status") === "failed"
      && u.searchParams.get("connection_id") === "c1")).toBe(true);
  });
});

it("shows not found for another workspace's connection", async () => {
  mockFetch({
    "GET /sync/connections/c1/health": { status: 404, body: { detail: "Connection not found" } },
    "GET /sync/runs": { status: 200, body: [] },
  });
  renderPage();
  expect(await screen.findByRole("alert")).toHaveTextContent("Connection not found");
  expect(screen.getByRole("link", { name: "All connections" })).toBeInTheDocument();
});

it("pauses a healthy connection after confirming, and offers no resume or reconnect", async () => {
  const spy = mockFetch({
    ...health(), "GET /sync/runs": { status: 200, body: [] },
    "POST /connections/c1/pause": { status: 200, body: { ...connection, state: "paused" } },
  });
  renderPage();
  const controls = await screen.findByRole("group", { name: "Connection controls" });
  expect(within(controls).queryByRole("button", { name: "Resume syncing" })).not.toBeInTheDocument();
  expect(within(controls).queryByRole("button", { name: "Reconnect" })).not.toBeInTheDocument();
  fireEvent.click(within(controls).getByRole("button", { name: "Pause syncing" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Syncing paused.");
  expect(posts(spy)).toEqual(["/connections/c1/pause"]);
});

it("resumes a paused connection", async () => {
  const spy = mockFetch({
    ...health({ state: "paused" }), "GET /sync/runs": { status: 200, body: [] },
    "POST /connections/c1/resume": { status: 200, body: connection },
  });
  renderPage();
  const controls = await screen.findByRole("group", { name: "Connection controls" });
  expect(within(controls).queryByRole("button", { name: "Pause syncing" })).not.toBeInTheDocument();
  fireEvent.click(within(controls).getByRole("button", { name: "Resume syncing" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Syncing resumed.");
  expect(posts(spy)).toEqual(["/connections/c1/resume"]);
});

it("reconnects with a new token sent in the body, never shown on the page", async () => {
  const spy = mockFetch({
    ...health({ state: "reconnect_needed", state_reason: "token revoked" }), "GET /sync/runs": { status: 200, body: [] },
    "POST /connections/c1/reconnect": { status: 200, body: connection },
  });
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Reconnect" }));
  const field = screen.getByLabelText("New access token");
  expect(field).toHaveAttribute("type", "password");
  fireEvent.change(field, { target: { value: "new-token-123" } });
  fireEvent.submit(field.closest("form")!);
  expect(await screen.findByRole("status")).toHaveTextContent("Reconnected.");
  expect(posts(spy)).toEqual(["/connections/c1/reconnect"]);
  const sent = spy.mock.calls.map(([input]) => input as Request).find((r) => r.method === "POST")!;
  expect(await sent.clone().json()).toEqual({ credentials: { access_token: "new-token-123" } });
  expect(document.body).not.toHaveTextContent("new-token-123");
});

it("disconnects after confirming, and a disconnected connection can only reconnect", async () => {
  const spy = mockFetch({
    ...health(), "GET /sync/runs": { status: 200, body: [] },
    "POST /connections/c1/disconnect": { status: 200, body: { ...connection, state: "disconnected" } },
  });
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }));
  expect(screen.getByRole("group", { name: /stored credential is destroyed/ })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Disconnected.");
  expect(posts(spy)).toEqual(["/connections/c1/disconnect"]);
});

it("shows the API's refusal next to the controls", async () => {
  mockFetch({
    ...health(), "GET /sync/runs": { status: 200, body: [] },
    "POST /connections/c1/pause": { status: 403, body: { detail: "Only the workspace owner can do that" } },
  });
  renderPage();
  fireEvent.click(await screen.findByRole("button", { name: "Pause syncing" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Only the workspace owner can do that");
});

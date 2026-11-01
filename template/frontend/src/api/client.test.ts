import { QueryClient } from "@tanstack/react-query";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch } from "@/test/utils";
import { setTokenProvider } from "./client";
import { ApiError } from "./errors";
import { accessQuery, meQuery } from "./queries";

afterEach(() => {
  vi.unstubAllGlobals();
  setTokenProvider(async () => null);
});

it("sends the bearer token and returns typed data", async () => {
  const spy = mockFetch({ "GET /me": { status: 200, body: { user_id: "u1", email: null, workspace: null } } });
  setTokenProvider(async () => "tok");
  const data = await new QueryClient().fetchQuery(meQuery);
  expect(data).toEqual({ user_id: "u1", email: null, workspace: null });
  const request = spy.mock.calls[0][0] as Request;
  expect(request.url).toBe("http://api.test/me");
  expect(request.headers.get("Authorization")).toBe("Bearer tok");
});

it("turns an error response into an ApiError with status and detail", async () => {
  mockFetch({ "GET /me/access": { status: 503, body: { detail: "lago is unavailable" } } });
  await expect(new QueryClient().fetchQuery(accessQuery)).rejects.toMatchObject({
    status: 503,
    detail: "lago is unavailable",
  });
  await expect(new QueryClient().fetchQuery(accessQuery)).rejects.toBeInstanceOf(ApiError);
});

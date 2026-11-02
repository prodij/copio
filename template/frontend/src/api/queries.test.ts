import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import { accessQuery, meQuery, retryAccess } from "./queries";

afterEach(() => vi.unstubAllGlobals());

it("turns a network failure into ApiError(0, Network error)", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("failed"); }));
  const err = await (meQuery.queryFn as () => Promise<unknown>)().catch((e: unknown) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err).toMatchObject({ status: 0, detail: "Network error" });
});

describe("retryAccess", () => {
  it("doesn't retry a 403, which only means no workspace yet", () => {
    expect(retryAccess(0, new ApiError(403, "No workspace for this user"))).toBe(false);
  });

  it("retries anything else up to 3 times", () => {
    expect(retryAccess(0, new ApiError(503, "down"))).toBe(true);
    expect(retryAccess(2, new ApiError(503, "down"))).toBe(true);
    expect(retryAccess(3, new ApiError(503, "down"))).toBe(false);
  });

  it("is on the shared query, so no page has to set it", () => {
    expect(accessQuery.retry).toBe(retryAccess);
  });
});

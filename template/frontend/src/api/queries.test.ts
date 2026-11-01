import { afterEach, expect, it, vi } from "vitest";
import { ApiError } from "./errors";
import { meQuery } from "./queries";

afterEach(() => vi.unstubAllGlobals());

it("turns a network failure into ApiError(0, Network error)", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("failed"); }));
  const err = await (meQuery.queryFn as () => Promise<unknown>)().catch((e: unknown) => e);
  expect(err).toBeInstanceOf(ApiError);
  expect(err).toMatchObject({ status: 0, detail: "Network error" });
});

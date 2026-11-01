import { describe, expect, it } from "vitest";
import { toApiError } from "./errors";

describe("toApiError", () => {
  it("uses FastAPI detail strings", () => {
    const err = toApiError(new Response(null, { status: 402 }), { detail: "no subscription" });
    expect(err.status).toBe(402);
    expect(err.detail).toBe("no subscription");
  });
  it("joins validation errors", () => {
    const err = toApiError(new Response(null, { status: 422 }), { detail: [{ msg: "too short" }, { msg: "bad" }] });
    expect(err.detail).toBe("too short; bad");
  });
  it("falls back to the status text", () => {
    const err = toApiError(new Response(null, { status: 503, statusText: "Service Unavailable" }), null);
    expect(err.detail).toBe("Service Unavailable");
  });
});

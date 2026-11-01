import { render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";

const um = vi.hoisted(() => ({
  signinRedirectCallback: vi.fn(async () => ({})),
  getUser: vi.fn(),
  signinRedirect: vi.fn(),
}));
vi.mock("./userManager", () => ({ userManager: um }));

import { AuthGate } from "./AuthGate";

afterEach(() => window.history.replaceState({}, "", "/"));

it("shows sign-in when signed out", async () => {
  um.getUser.mockResolvedValue(null);
  render(<AuthGate>app</AuthGate>);
  expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
});

it("exchanges the callback code once even under StrictMode", async () => {
  window.history.replaceState({}, "", "/callback?code=x&state=y");
  um.getUser.mockResolvedValue({ expired: false, access_token: "t" });
  render(<StrictMode><AuthGate>app</AuthGate></StrictMode>);
  expect(await screen.findByText("app")).toBeInTheDocument();
  expect(um.signinRedirectCallback).toHaveBeenCalledTimes(1);
});

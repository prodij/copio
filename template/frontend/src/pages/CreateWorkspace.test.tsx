import { fireEvent, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { mockFetch, renderWithQuery } from "@/test/utils";
import { CreateWorkspace } from "./CreateWorkspace";

vi.mock("@/auth/userManager", () => ({ userManager: { signinSilent: vi.fn(async () => null) } }));
afterEach(() => vi.unstubAllGlobals());

it("creates the workspace then refreshes the token", async () => {
  const { userManager } = await import("@/auth/userManager");
  mockFetch({ "POST /workspaces": { status: 201, body: { id: "w1", name: "Acme", status: "ready" } } });
  renderWithQuery(<CreateWorkspace />);
  fireEvent.change(screen.getByLabelText("Workspace name"), { target: { value: "Acme" } });
  fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));
  await vi.waitFor(() => expect(userManager.signinSilent).toHaveBeenCalled());
});

it("disables submit for a blank name", () => {
  renderWithQuery(<CreateWorkspace />);
  expect(screen.getByRole("button", { name: "Create workspace" })).toBeDisabled();
});

it("shows the API error and skips the token refresh when creation fails", async () => {
  const { userManager } = await import("@/auth/userManager");
  vi.mocked(userManager.signinSilent).mockClear();
  mockFetch({ "POST /workspaces": { status: 503, body: { detail: "zitadel is unavailable" } } });
  renderWithQuery(<CreateWorkspace />);
  fireEvent.change(screen.getByLabelText("Workspace name"), { target: { value: "Acme" } });
  fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));
  expect(await screen.findByText("zitadel is unavailable")).toBeInTheDocument();
  expect(userManager.signinSilent).not.toHaveBeenCalled();
});

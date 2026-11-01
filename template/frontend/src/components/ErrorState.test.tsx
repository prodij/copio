import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ApiError } from "@/api/errors";
import { ErrorState } from "./ErrorState";
import { Unavailable } from "./Unavailable";

it("shows status and detail", () => {
  render(<ErrorState error={new ApiError(503, "Lago is unavailable")} />);
  expect(screen.getByText("503")).toBeInTheDocument();
  expect(screen.getByText("Lago is unavailable")).toBeInTheDocument();
});

it("unavailable never renders zero", () => {
  render(<Unavailable />);
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  expect(screen.queryByText("0")).toBeNull();
});

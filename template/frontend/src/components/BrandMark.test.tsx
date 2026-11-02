import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { BrandMark } from "./BrandMark";

it("shows the generated logo and the product's name", () => {
  document.title = "Acme Reports";
  const { container } = render(<BrandMark />);
  expect(screen.getByText("Acme Reports")).toBeInTheDocument();
  expect(container.querySelector("img")).toHaveAttribute("src", "/logo.svg");
});

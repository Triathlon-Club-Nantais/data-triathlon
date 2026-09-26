import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IconButton } from "./IconButton";

describe("IconButton", () => {
  it("gives the close variant the public touch target below md (#1079)", () => {
    render(<IconButton variant="close" aria-label="Fermer">×</IconButton>);

    expect(screen.getByRole("button", { name: "Fermer" })).toHaveClass("tcn-cible-tactile");
  });
});

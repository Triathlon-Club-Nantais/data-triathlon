import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PendingBadge } from "./PendingBadge";

describe("PendingBadge", () => {
  it("affiche une mention explicite d'attente de validation", () => {
    render(<PendingBadge />);
    expect(screen.getByText(/en attente de validation/i)).toBeInTheDocument();
  });
});

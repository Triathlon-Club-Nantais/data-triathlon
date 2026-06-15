import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it("affiche le sigle DNS avec le libellé complet en title", () => {
    render(<StatusBadge status="DNS" />);
    const badge = screen.getByText("DNS");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("title", "Non partant");
  });

  it("affiche DNF et DSQ", () => {
    const { rerender } = render(<StatusBadge status="DNF" />);
    expect(screen.getByText("DNF")).toHaveAttribute("title", "Abandon");
    rerender(<StatusBadge status="DSQ" />);
    expect(screen.getByText("DSQ")).toHaveAttribute("title", "Disqualifié");
  });

  it("normalise la casse du statut", () => {
    render(<StatusBadge status="dns" />);
    expect(screen.getByText("DNS")).toBeInTheDocument();
  });

  it("n'affiche rien pour un finisher", () => {
    const { container } = render(<StatusBadge status="finisher" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("n'affiche rien pour un statut absent", () => {
    const { container } = render(<StatusBadge status={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

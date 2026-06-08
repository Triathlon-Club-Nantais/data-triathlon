import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SportBadge } from "./SportBadge";

describe("SportBadge", () => {
  it("affiche le libellé lisible du type", () => {
    render(<SportBadge type="triathlon-m" />);
    expect(screen.getByText("Triathlon M")).toBeInTheDocument();
  });
  it("retombe sur le type brut si inconnu", () => {
    render(<SportBadge type="xyz" />);
    expect(screen.getByText("xyz")).toBeInTheDocument();
  });
  it("ne rend rien si type vide", () => {
    const { container } = render(<SportBadge type="" />);
    expect(container).toBeEmptyDOMElement();
  });
});

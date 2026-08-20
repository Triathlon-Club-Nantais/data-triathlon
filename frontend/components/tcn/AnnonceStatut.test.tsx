import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnnonceStatut } from "./AnnonceStatut";

describe("AnnonceStatut", () => {
  it("rend le texte dans une région role=status visuellement masquée", () => {
    render(<AnnonceStatut texte="48 épreuves, 312 résultats" />);
    const region = screen.getByRole("status");
    expect(region).toHaveTextContent("48 épreuves, 312 résultats");
    expect(region).toHaveClass("sr-only");
  });

  it("porte aria-live=polite et aria-atomic=true pour lire l'annonce en entier", () => {
    render(<AnnonceStatut texte="X" />);
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-atomic", "true");
  });

  it("ne porte pas aria-busy par défaut", () => {
    render(<AnnonceStatut texte="X" />);
    expect(screen.getByRole("status")).not.toHaveAttribute("aria-busy");
  });

  it("porte aria-busy=true quand busy est passé", () => {
    render(<AnnonceStatut texte="X" busy />);
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });
});

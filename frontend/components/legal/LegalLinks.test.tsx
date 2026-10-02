import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { LegalLinks } from "./LegalLinks";

describe("LegalLinks (#333)", () => {
  it("rend les trois textes légaux, dans l'ordre du pied de page", () => {
    render(<LegalLinks />);
    const nav = screen.getByRole("navigation", { name: "Informations légales" });
    const liens = within(nav).getAllByRole("link");
    expect(liens.map((lien) => [lien.textContent, lien.getAttribute("href")])).toEqual([
      ["Mentions légales", "/mentions-legales"],
      ["Confidentialité", "/confidentialite"],
      ["Conditions d'utilisation", "/cgu"],
    ]);
  });

  it("agrandit la cible tactile sans changer le texte (WCAG 2.5.8)", () => {
    render(<LegalLinks />);
    for (const lien of screen.getAllByRole("link")) {
      expect(lien).toHaveClass("py-1.5", "-my-1.5");
    }
  });
});

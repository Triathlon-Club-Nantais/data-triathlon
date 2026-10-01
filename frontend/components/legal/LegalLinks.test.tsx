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
});

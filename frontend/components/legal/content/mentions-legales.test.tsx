import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LegalPage } from "../LegalPage";
import { LEGAL_NOTICE } from "./mentions-legales";

function rendre() {
  render(<LegalPage document={LEGAL_NOTICE} />);
  return document.body.textContent ?? "";
}

describe("Mentions légales (#333)", () => {
  it("identifie l'éditeur et le directeur de la publication", () => {
    const texte = rendre();
    expect(texte).toContain("Triathlon Club Nantais");
    expect(texte).toContain("2 boulevard René Coty");
    expect(texte).toContain("44100 Nantes");
    expect(texte).toContain("403 516 347 00016");
    expect(texte).toContain("Aurélien Gantier");
  });

  it("nomme les hébergeurs avec leur adresse", () => {
    const texte = rendre();
    expect(texte).toContain("Vercel Inc.");
    expect(texte).toContain("Covina");
    expect(texte).toContain("Render Services, Inc.");
    expect(texte).toContain("San Francisco");
    expect(texte).toContain("Microsoft Ireland Operations Ltd");
    expect(texte).toContain("Dublin");
  });

  it("donne un contact et renvoie vers la politique de confidentialité", () => {
    rendre();
    for (const lien of screen.getAllByRole("link", { name: "president@triathlon-club-nantais.com" })) {
      expect(lien).toHaveAttribute("href", "mailto:president@triathlon-club-nantais.com");
    }
    expect(screen.getByRole("link", { name: "politique de confidentialité" })).toHaveAttribute(
      "href",
      "/confidentialite",
    );
  });
});

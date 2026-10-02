import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LegalPage } from "../LegalPage";
import { TERMS_OF_USE } from "./cgu";

function rendre() {
  render(<LegalPage document={TERMS_OF_USE} />);
  return document.body.textContent ?? "";
}

function rubrique(title: RegExp) {
  return screen.getByRole("heading", { level: 2, name: title });
}

describe("Conditions d'utilisation (#333)", () => {
  it("couvre l'objet du site, son accès, la saisie manuelle, les signalements et la responsabilité", () => {
    rendre();
    rubrique(/objet/i);
    rubrique(/accès/i);
    rubrique(/saisie manuelle/i);
    rubrique(/signalements/i);
    rubrique(/responsabilité/i);
    rubrique(/correction/i);
  });

  it("dit ce qu'un adhérent s'engage à déclarer et qui valide", () => {
    const texte = rendre();
    expect(texte).toMatch(/code d'accès/i);
    expect(texte).toMatch(/réellement obtenu/i);
    expect(texte).toMatch(/preuve/i);
    expect(texte).toMatch(/bénévole/i);
  });

  it("borne la responsabilité sur les données des chronométreurs", () => {
    expect(rendre()).toMatch(/chronométreurs/i);
  });

  it("renvoie vers la politique de confidentialité pour le retrait de ses résultats", () => {
    rendre();
    expect(screen.getByRole("link", { name: "politique de confidentialité" })).toHaveAttribute(
      "href",
      "/confidentialite",
    );
  });
});

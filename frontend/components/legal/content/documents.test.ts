import { describe, expect, it } from "vitest";
import type { LegalDocument } from "../types";
import { TERMS_OF_USE } from "./cgu";
import { PRIVACY_POLICY } from "./confidentialite";
import { LEGAL_NOTICE } from "./mentions-legales";

const DOCUMENTS: [string, LegalDocument][] = [
  ["mentions légales", LEGAL_NOTICE],
  ["politique de confidentialité", PRIVACY_POLICY],
  ["conditions d'utilisation", TERMS_OF_USE],
];

describe.each(DOCUMENTS)("Texte légal : %s (#333)", (_nom, legalDocument) => {
  it("porte une date de mise à jour ISO valide, pas dans le futur", () => {
    const [year, month, day] = legalDocument.updatedAt.split("-").map(Number);
    const date = new Date(year, month - 1, day);
    // Un 31 février se normaliserait en silence au 3 mars : on exige l'aller-retour.
    expect([date.getFullYear(), date.getMonth() + 1, date.getDate()]).toEqual([year, month, day]);
    expect(legalDocument.updatedAt).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(date.getTime()).toBeLessThanOrEqual(Date.now());
  });

  it("donne une ancre unique à chaque rubrique", () => {
    const ids = legalDocument.sections.map((section) => section.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

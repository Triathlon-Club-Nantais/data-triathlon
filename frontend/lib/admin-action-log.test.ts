import { describe, it, expect } from "vitest";
import { actionLabel, formatPayload } from "./admin-action-log";

describe("actionLabel", () => {
  it("traduit un geste connu", () => {
    expect(actionLabel("course.delete")).toBe("Suppression d'une épreuve");
  });

  it("retombe sur le code brut pour un geste inconnu", () => {
    expect(actionLabel("future.action")).toBe("future.action");
  });
});

describe("formatPayload", () => {
  it("rend un tableau vide pour un payload absent", () => {
    expect(formatPayload(null)).toEqual([]);
  });

  it("traduit les clés connues, garde la clé brute pour une clé inconnue", () => {
    const lignes = formatPayload({ participations_deleted: 5, cle_inconnue: "x" });

    expect(lignes).toContainEqual({ label: "Résultats détruits", value: "5" });
    expect(lignes).toContainEqual({ label: "cle_inconnue", value: "x" });
  });

  it("rend un diff champ par champ pour before/after objets, sans les champs inchangés", () => {
    const lignes = formatPayload({
      before: { nom: "Dupont", club: "TCN" },
      after: { nom: "Dupond", club: "TCN" },
    });

    expect(lignes).toEqual([{ label: "Nom", value: "Dupont → Dupond" }]);
  });

  it("rend un diff simple pour before/after scalaires", () => {
    const lignes = formatPayload({ before: null, after: true, notes: "vérifié à la main" });

    expect(lignes).toContainEqual({ label: "Modification", value: "— → oui" });
    expect(lignes).toContainEqual({ label: "Note", value: "vérifié à la main" });
  });

  it("aplatit un objet imbriqué en une ligne lisible, clés traduites", () => {
    const lignes = formatPayload({
      absorbed: { name: "Triathlon d'Ancenis", event_date: "2026-05-01" },
    });

    expect(lignes).toEqual([
      {
        label: "Épreuve absorbée",
        value: "Nom de l'épreuve : Triathlon d'Ancenis, Date : 2026-05-01",
      },
    ]);
  });

  it("rend oui/non pour un booléen, un tiret pour null", () => {
    const lignes = formatPayload({ is_relay: false, source_added: null });

    expect(lignes).toContainEqual({ label: "Relais", value: "non" });
    expect(lignes).toContainEqual({ label: "Source ajoutée", value: "—" });
  });
});

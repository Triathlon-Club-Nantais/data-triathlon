import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { actionLabel, detailLines, formatPayload } from "./admin-action-log";

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

  it("rend un tableau comme un décompte suivi des valeurs, jamais un CSV nu", () => {
    const lignes = formatPayload({ athletes_purged: [12, 43, 88] });

    expect(lignes).toContainEqual({ label: "Fiches coureur purgées", value: "3 (12, 43, 88)" });
  });

  it("rend un tableau vide comme « aucun »", () => {
    const lignes = formatPayload({ athletes_purged: [] });

    expect(lignes).toContainEqual({ label: "Fiches coureur purgées", value: "aucun" });
  });
});

describe("catalogue coverage (#1043)", () => {
  function codesEmis(dossier: string): string[] {
    return readdirSync(dossier).flatMap((nom) => {
      const chemin = join(dossier, nom);
      if (statSync(chemin).isDirectory()) return codesEmis(chemin);
      if (!nom.endsWith(".py")) return [];
      const source = readFileSync(chemin, "utf8");
      return [...source.matchAll(/(?:action=|_ACTION = )"([a-z_.]+)"/g)].map((m) => m[1]);
    });
  }

  it("translates every action code the backend records", () => {
    const codes = [...new Set(codesEmis(join(__dirname, "..", "..", "backend", "app")))];
    expect(codes.length).toBeGreaterThan(20);
    expect(codes.filter((code) => actionLabel(code) === code)).toEqual([]);
  });

  it("translates the season, volunteering and source payload keys", () => {
    const lignes = formatPayload({ season: 2026, action_id: 4, url: "https://x", provider: "klikego" });

    expect(lignes.map((l) => l.label)).toEqual(["Saison", "Déclaration de bénévolat", "URL", "Fournisseur"]);
  });
});

describe("links and target entity (#1043)", () => {
  it("links athlete and course ids to their public pages", () => {
    const lignes = formatPayload({ from_athlete_id: 55749, course_id: 12 });

    expect(lignes).toContainEqual({ label: "Depuis le coureur", value: "55749", href: "/athletes/55749" });
    expect(lignes).toContainEqual({ label: "Épreuve", value: "12", href: "/courses/12" });
  });

  it("names the target entity when the payload is empty", () => {
    expect(detailLines({ entity_type: "club_alias", entity_id: 3, payload: null })).toEqual([
      { label: "Variante de club", value: "n° 3" },
    ]);
    expect(detailLines({ entity_type: "athlete", entity_id: 9, payload: null })).toEqual([
      { label: "Coureur", value: "9", href: "/athletes/9" },
    ]);
  });

  it("keeps the payload lines when there are some", () => {
    expect(detailLines({ entity_type: "athlete", entity_id: 9, payload: { season: 2026 } })).toEqual([
      { label: "Saison", value: "2026" },
    ]);
  });
});

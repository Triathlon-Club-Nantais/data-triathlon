import { describe, it, expect } from "vitest";
import { NAV, ROLE, ecran, estVisible } from "./nav.config";

/** Les destinations du back-office : celles que le sommaire `/admin` annonce. */
const ECRANS_ADMIN = NAV.flatMap((s) => s.items).filter(
  (i) => i.href?.startsWith("/admin/") && !i.soon,
);

describe("nav.config", () => {
  it("décrit chaque écran d'administration", () => {
    // `ecran()` lève sur une entrée sans phrase, et c'est un `PageHeader` de
    // page qui l'appelle : l'oubli casserait l'écran, pas seulement sa tuile.
    for (const item of ECRANS_ADMIN) {
      expect(() => ecran(item.href as string), item.href).not.toThrow();
    }
  });

  it("n'annonce aucun écran d'administration sans pouvoir nommé", () => {
    // Une entrée sans `permission` est proposée à qui vient de se connecter et
    // n'y peut rien faire — le défaut relevé sur « Épreuves » (ADM-6).
    for (const item of ECRANS_ADMIN) {
      expect(item.permission, item.href).toBeTruthy();
    }
  });
});

describe("nav.config — Club (#487)", () => {
  it("annonce « Espace club » vers /club", () => {
    // PROF-1 : la page la plus riche du périmètre n'était atteignable qu'en
    // tapant l'URL — l'entrée existait sans `href`, donc `estVisible` la taisait.
    const item = NAV.flatMap((s) => s.items).find((i) => i.id === "vueclub");
    expect(item).toBeDefined();
    expect(item?.href).toBe("/club");
    expect(estVisible(item!, new Set(), ROLE.ANON)).toBe(true);
  });
});

describe("nav.config — pages en avant-première (#811)", () => {
  const ATHLETES_SAISON = NAV.flatMap((s) => s.items).find((i) => i.id === "athletes-saison")!;
  const CARTE = NAV.flatMap((s) => s.items).find((i) => i.id === "carte")!;

  it("masque « Athlètes par saison » sans le pouvoir pages:preview", () => {
    expect(estVisible(ATHLETES_SAISON, new Set(), ROLE.ANON)).toBe(false);
    expect(estVisible(ATHLETES_SAISON, new Set(), ROLE.CONNECTED)).toBe(false);
  });

  it("montre « Athlètes par saison » avec le pouvoir pages:preview", () => {
    expect(estVisible(ATHLETES_SAISON, new Set(["pages:preview"]), ROLE.CONNECTED)).toBe(true);
  });

  it("garde « Carte » masquée par défaut malgré son href", () => {
    expect(CARTE.href).toBe("/carte");
    expect(estVisible(CARTE, new Set(), ROLE.ANON)).toBe(false);
  });

  it("montre « Carte » à qui détient pages:preview", () => {
    expect(estVisible(CARTE, new Set(["pages:preview"]), ROLE.CONNECTED)).toBe(true);
  });

  it("garde une entrée `soon` sans permission nommée invisible même pourvu(e)", () => {
    // `stats` reste `soon` sans `permission` : aucun pouvoir ne doit pouvoir la
    // débloquer par accident (elle n'a de toute façon pas de `href`).
    const STATS = NAV.flatMap((s) => s.items).find((i) => i.id === "stats")!;
    expect(estVisible(STATS, new Set(["pages:preview"]), ROLE.CONNECTED)).toBe(false);
  });
});

describe("nav.config — Bénévolat et Bénévoles (#830, #832)", () => {
  it("annonce « Bénévolat » vers /benevolat, visible sans pouvoir", () => {
    const item = NAV.flatMap((s) => s.items).find((i) => i.id === "benevolat");
    expect(item).toBeDefined();
    expect(item?.href).toBe("/benevolat");
    expect(estVisible(item!, new Set(), ROLE.ANON)).toBe(true);
  });

  it("annonce « Bénévoles » vers /benevoles, visible sans pouvoir", () => {
    const item = NAV.flatMap((s) => s.items).find((i) => i.id === "benevoles");
    expect(item).toBeDefined();
    expect(item?.href).toBe("/benevoles");
    expect(estVisible(item!, new Set(), ROLE.ANON)).toBe(true);
  });
});

describe("permission en OU", () => {
  const MAINTENANCE = NAV.flatMap((s) => s.items).find((i) => i.id === "a-maintenance")!;

  it("annonce la maintenance à qui ne détient que la purge des résultats", () => {
    expect(estVisible(MAINTENANCE, new Set(["participations:wipe_all"]), ROLE.CONNECTED)).toBe(true);
  });

  it("l'annonce aussi à qui ne détient que la purge des épreuves", () => {
    expect(estVisible(MAINTENANCE, new Set(["courses:wipe_all"]), ROLE.CONNECTED)).toBe(true);
  });

  it("ne l'annonce pas à qui n'a ni l'une ni l'autre", () => {
    expect(estVisible(MAINTENANCE, new Set(["courses:write"]), ROLE.CONNECTED)).toBe(false);
  });
});

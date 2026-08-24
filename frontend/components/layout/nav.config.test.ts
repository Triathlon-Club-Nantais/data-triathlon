import { describe, it, expect } from "vitest";
import { NAV, ROLE, ecran, estVisible, type NavItem } from "./nav.config";

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
    expect(item?.href).toBe("/club");
    expect(estVisible(item as NavItem, new Set(), ROLE.ANON)).toBe(true);
  });
});

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { Metadata } from "next";
import { describe, expect, it, vi } from "vitest";
import { ecran } from "@/components/layout/nav.config";

vi.mock("server-only", () => ({}));

/**
 * Un titre de document par écran (#1040, WCAG 2.4.2). Le gabarit `%s · TCN`
 * du layout racine les complète. Chaque module qui porte le titre d'une route
 * (la page, ou le layout d'une page client) est listé ici.
 */
const TITRES: [string, () => Promise<{ metadata?: Metadata }>, string][] = [
  ["/dashboard", () => import("./(public_restricted)/dashboard/page"), "Tableau de bord"],
  ["/resultats", () => import("./(public_restricted)/resultats/page"), "Résultats"],
  ["/club", () => import("./(public_restricted)/club/page"), "Espace club"],
  ["/club/athletes", () => import("./(public_restricted)/club/athletes/page"), "Athlètes par saison"],
  ["/guide", () => import("./(public_restricted)/guide/page"), "Guide utilisateur"],
  ["/ajouter", () => import("./(public_restricted)/ajouter/page"), "Ajouter une épreuve"],
  ["/carte", () => import("./(public_restricted)/carte/layout"), "Carte des épreuves"],
  ["/benevolat", () => import("./(public_restricted)/benevolat/page"), "Bénévolat"],
  ["/courses/[id]", () => import("./(public_restricted)/courses/[id]/page"), "Épreuve"],
  ["/athletes/[id]", () => import("./(public_restricted)/athletes/[id]/page"), "Athlète"],
  [
    "/courses/[id]/participations/[participationId]",
    () => import("./(public_restricted)/courses/[id]/participations/[participationId]/page"),
    "Résultat individuel",
  ],
  ["/acces", () => import("./acces/page"), "Code d'accès"],
  ["/mentions-legales", () => import("./mentions-legales/page"), "Mentions légales"],
  ["/confidentialite", () => import("./confidentialite/page"), "Politique de confidentialité"],
  ["/cgu", () => import("./cgu/page"), "Conditions d'utilisation"],
  ["/login", () => import("./login/layout"), "Connexion"],
  ["/benevoles", () => import("./benevoles/layout"), "Vérification des résultats"],
  ["404", () => import("./not-found"), "Page introuvable"],
  ["/admin", () => import("./admin/page"), "Back-office"],
  ["/admin/guide", () => import("./admin/guide/page"), "Guide d'administration"],
  ["/admin/jeunes/[id]", () => import("./admin/jeunes/[id]/page"), "Profil"],
  ["/admin/jeunes/appel/[id]", () => import("./admin/jeunes/appel/[id]/page"), "Appel"],
];

/** Écrans d'administration : le titre vient de `nav.config.ts`, source unique (#497). */
const ECRANS: [string, () => Promise<{ metadata?: Metadata }>][] = [
  ["/admin/acces", () => import("./admin/acces/page")],
  ["/admin/batches", () => import("./admin/batches/page")],
  ["/admin/benevolat", () => import("./admin/benevolat/page")],
  ["/admin/courses", () => import("./admin/courses/page")],
  ["/admin/doublons", () => import("./admin/doublons/page")],
  ["/admin/droits", () => import("./admin/droits/page")],
  ["/admin/fournisseurs", () => import("./admin/fournisseurs/page")],
  ["/admin/groupes", () => import("./admin/groupes/page")],
  ["/admin/jeunes", () => import("./admin/jeunes/page")],
  ["/admin/jeunes/calendrier", () => import("./admin/jeunes/calendrier/page")],
  ["/admin/jeunes/appel", () => import("./admin/jeunes/appel/layout")],
  ["/admin/journal", () => import("./admin/journal/page")],
  ["/admin/maintenance", () => import("./admin/maintenance/layout")],
  ["/admin/portee-compteurs", () => import("./admin/portee-compteurs/layout")],
  ["/admin/quality", () => import("./admin/quality/page")],
  ["/admin/retours-utilisateurs", () => import("./admin/retours-utilisateurs/page")],
  ["/admin/utilisateurs", () => import("./admin/utilisateurs/page")],
  ["/admin/variantes-club", () => import("./admin/variantes-club/layout")],
];

describe("titres de document (#1040)", () => {
  it.each(TITRES)("%s porte son titre", async (_route, charger, titre) => {
    expect((await charger()).metadata?.title).toBe(titre);
  });

  it.each(ECRANS)("%s reprend le titre de son écran", async (route, charger) => {
    expect((await charger()).metadata?.title).toBe(ecran(route).title);
  });

  it.each([
    "./(public_restricted)/courses/[id]/page.tsx",
    "./(public_restricted)/athletes/[id]/page.tsx",
    "./(public_restricted)/courses/[id]/participations/[participationId]/page.tsx",
  ])("%s ne nomme pas la ressource avant la garde d'accès", (chemin) => {
    // `generateMetadata` se résout indépendamment du layout qui garde l'accès
    // (#509) : un nom d'épreuve ou d'athlète y partirait vers un visiteur sans code.
    const source = readFileSync(fileURLToPath(new URL(chemin, import.meta.url)), "utf8");

    expect(source).not.toContain("generateMetadata");
  });
});

import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Contrat des fiches dynamiques absentes (#1064) : **200 et `noindex`**, pas 404.
 *
 * Chaque route porte un `loading.tsx`, donc une frontière Suspense : le statut
 * 200 part avec le squelette, avant que la page n'appelle `notFound()`. Next
 * injecte alors `<meta name="robots" content="noindex">` dans le HTML streamé.
 * Arbitrage retenu : on garde le squelette. Aucun test unitaire ne rend un flux
 * Next réel ; ce fichier fixe les deux moitiés du contrat qui se lisent sans
 * serveur, et la mesure `curl` sur un build de production reste la preuve.
 */
const GROUPE = join(__dirname, "(public_restricted)");

const ROUTES = [
  { page: "athletes/[id]", loading: "athletes/[id]" },
  { page: "courses/[id]", loading: "courses/[id]" },
  { page: "courses/[id]/participations/[participationId]", loading: "courses/[id]/participations/[participationId]" },
];

describe("fiches dynamiques absentes : 200 streamé et noindex (#1064)", () => {
  it.each(ROUTES)("$page appelle notFound() sous une frontière loading.tsx", ({ page, loading }) => {
    const source = readFileSync(join(GROUPE, page, "page.tsx"), "utf8");
    expect(source).toMatch(/notFound\(\)/);
    // Si ce fichier disparaît, la route répond un vrai 404 : le contrat change,
    // et `frontend/AGENTS.md` avec lui.
    expect(existsSync(join(GROUPE, loading, "loading.tsx"))).toBe(true);
  });

  it("Next injecte `noindex` pour un notFound() levé après le début du flux", () => {
    const require = createRequire(import.meta.url);
    const nextDist = dirname(require.resolve("next/package.json"));
    const inserted = readFileSync(
      join(nextDist, "dist/server/app-render/make-get-server-inserted-html.js"),
      "utf8",
    );
    // Canari de montée de version : la branche qui transforme une erreur
    // d'accès HTTP (notFound, forbidden…) capturée en cours de flux en balise.
    const branche = inserted.slice(inserted.indexOf("isHTTPAccessFallbackError)(error)"));
    expect(branche).not.toBe(inserted);
    expect(branche.slice(0, 300)).toMatch(/name: "robots",\s*content: "noindex"/);
  });
});

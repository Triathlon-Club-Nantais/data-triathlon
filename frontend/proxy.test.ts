import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { buildCspPolicy, proxy } from "./proxy";

function requeteAvec(cookies: Record<string, string>) {
  const requete = new NextRequest("https://exemple.fr/dashboard");
  for (const [nom, valeur] of Object.entries(cookies)) {
    requete.cookies.set(nom, valeur);
  }
  return requete;
}

const CSP = "content-security-policy";

/** Nom de l'en-tête tel que `NextResponse.next({ request })` l'encode sur la
 * réponse pour le renderer (`server/web/spec-extension/response.js`). */
const CSP_TRANSMISE = `x-middleware-request-${CSP}`;

/**
 * Extraction du nonce **telle que Next la fait**, recopiée depuis
 * `node_modules/next/dist/server/app-render/get-script-nonce-from-header.js` :
 * la regex et la recherche par `startsWith` comprises. Reproduire l'algorithme
 * plutôt qu'assener une regex maison est ce qui rend le test parlant — il
 * échoue si l'ordre des directives change, pas seulement leur contenu.
 */
function nonceLuParNext(politique: string): string | undefined {
  const directives = politique.split(";").map((directive) => directive.trim());
  const directive =
    directives.find((d) => d.startsWith("script-src")) ??
    directives.find((d) => d.startsWith("default-src"));
  if (!directive) return undefined;
  for (const source of directive.split(/\s+/).slice(1)) {
    const trouve = source.trim().match(/^'nonce-([A-Za-z0-9+/_-]+={0,2})'$/);
    if (trouve) return trouve[1];
  }
}

function directive(politique: string, nom: string): string | undefined {
  return politique
    .split(";")
    .map((entree) => entree.trim())
    .find((entree) => entree === nom || entree.startsWith(`${nom} `));
}

describe("proxy", () => {
  it("pose tcn_logged_in pour une session déjà ouverte sans le cookie de présence", () => {
    // #427 — après un déploiement, un visiteur déjà connecté porte
    // `__Host-tcn_session` (posé avant ce correctif) mais pas encore
    // `tcn_logged_in` : sans cette auto-guérison, `useSession` le traiterait
    // en anonyme jusqu'à sa prochaine connexion ou l'expiration (7 jours).
    const reponse = proxy(requeteAvec({ "__Host-tcn_session": "jeton" }));

    expect(reponse.cookies.get("tcn_logged_in")?.value).toBe("1");
  });

  it("pose le cookie aussi en développement, où le nom ne porte pas le préfixe __Host-", () => {
    const reponse = proxy(requeteAvec({ tcn_session: "jeton" }));

    expect(reponse.cookies.get("tcn_logged_in")?.value).toBe("1");
  });

  it("ne pose rien pour un visiteur réellement anonyme", () => {
    const reponse = proxy(requeteAvec({}));

    expect(reponse.cookies.get("tcn_logged_in")).toBeUndefined();
  });

  it("ne réémet pas de Set-Cookie si le cookie de présence est déjà là", () => {
    const reponse = proxy(
      requeteAvec({ "__Host-tcn_session": "jeton", tcn_logged_in: "1" }),
    );

    expect(reponse.headers.get("set-cookie")).toBeNull();
  });
});

describe("proxy — Content-Security-Policy (#448, bascule #570)", () => {
  it("pose la politique en mode bloquant, plus en observation", () => {
    // Retournement du verrou de #453 : la phase d'observation est close, et un
    // retour à `Report-Only` ne protégerait plus de rien.
    const reponse = proxy(requeteAvec({}));

    expect(reponse.headers.get(CSP)).toBeTruthy();
    expect(reponse.headers.get("content-security-policy-report-only")).toBeNull();
  });

  it("transmet la politique dans les en-têtes de la requête, seul endroit où Next lit le nonce", () => {
    // `app-render.js:209` lit la CSP dans les en-têtes de la **requête**. Un
    // proxy qui n'écrit que la réponse produit une politique correcte et un
    // HTML sans nonce : chaque script de Next serait alors rapporté en
    // violation. C'est l'invariant qui casse le plus silencieusement.
    const reponse = proxy(requeteAvec({}));

    const transmise = reponse.headers.get(CSP_TRANSMISE);
    expect(transmise).toBeTruthy();
    expect(transmise).toBe(reponse.headers.get(CSP));
  });

  it("expose un nonce que l'extraction de Next sait retrouver", () => {
    const reponse = proxy(requeteAvec({}));

    expect(nonceLuParNext(reponse.headers.get(CSP)!)).toBeTruthy();
  });

  it("renouvelle le nonce à chaque requête", () => {
    // Un nonce rejoué n'est plus imprévisible, donc ne protège plus de rien.
    const premier = nonceLuParNext(proxy(requeteAvec({})).headers.get(CSP)!);
    const second = nonceLuParNext(proxy(requeteAvec({})).headers.get(CSP)!);

    expect(premier).not.toBe(second);
  });

  it("pose la CSP même pour un visiteur anonyme, que la logique de #441 court-circuitait", () => {
    const anonyme = proxy(requeteAvec({}));
    const dejaSignale = proxy(
      requeteAvec({ "__Host-tcn_session": "jeton", tcn_logged_in: "1" }),
    );

    expect(anonyme.headers.get(CSP)).toBeTruthy();
    expect(dejaSignale.headers.get(CSP)).toBeTruthy();
  });
});

describe("buildCspPolicy", () => {
  it("borne la concession de l'inline aux attributs style, sans ouvrir les éléments <style>", () => {
    // 412 attributs `style` en ligne dans le front, et un nonce ne s'applique
    // jamais à un attribut. Écrire `style-src 'unsafe-inline'` à la place
    // ouvrirait aussi les `<style>` et les feuilles.
    const politique = buildCspPolicy("abc", { dev: false });

    expect(directive(politique, "style-src-attr")).toBe(
      "style-src-attr 'unsafe-inline'",
    );
    expect(directive(politique, "style-src")).not.toContain("'unsafe-inline'");
  });

  it("autorise en images les deux seules origines tierces du front", () => {
    // Tuiles OSM et les trois marqueurs Leaflet ; tout le reste du trafic
    // navigateur est même-origine, PostHog compris (proxy inverse `/ingest`).
    const imgSrc = directive(buildCspPolicy("abc", { dev: false }), "img-src");

    expect(imgSrc).toContain("https://*.tile.openstreetmap.org");
    expect(imgSrc).toContain("https://unpkg.com");
  });

  it("couvre les scripts par 'strict-dynamic', ce qui rend tout hash de script inutile", () => {
    // L'absence de hash dans `script-src` est le fonctionnement nominal, pas un
    // oubli : les `<script>` du rendu serveur portent le nonce, et tout ce
    // qu'ils insèrent ensuite passe par propagation. Ce test est le garde-fou
    // de cette explication — retirer `'strict-dynamic'` sans épingler quoi que
    // ce soit casserait `array.js`, que `posthog-js` insère lui-même.
    const scriptSrc = directive(buildCspPolicy("abc", { dev: false }), "script-src")!;

    expect(scriptSrc).toContain("'nonce-abc'");
    expect(scriptSrc).toContain("'strict-dynamic'");
  });

  it("n'autorise 'unsafe-eval' qu'en développement", () => {
    // React s'en sert pour reconstruire les piles d'erreurs serveur dans le
    // navigateur ; ni React ni Next n'en ont besoin en production.
    expect(buildCspPolicy("abc", { dev: true })).toContain("'unsafe-eval'");
    expect(buildCspPolicy("abc", { dev: false })).not.toContain("'unsafe-eval'");
  });

  it("ne réclame la promotion en HTTPS qu'en production", () => {
    // En développement l'app est servie en clair : la directive y casserait
    // toutes les sous-ressources.
    expect(buildCspPolicy("abc", { dev: false })).toContain(
      "upgrade-insecure-requests",
    );
    expect(buildCspPolicy("abc", { dev: true })).not.toContain(
      "upgrade-insecure-requests",
    );
  });
});

describe("buildCspPolicy — les deux hashes de sonner (#570)", () => {
  /**
   * Le CSS que `sonner` injecte au niveau module, lu **dans le paquet
   * installé** : c'est ce qui fait de ce test un détecteur de dérive. Un
   * `npm update sonner` change la chaîne, donc le hash, donc ce test casse —
   * au lieu de laisser les toasts perdre leur style en production.
   */
  function cssInjecteParSonner(): string {
    const source = readFileSync(
      new URL("./node_modules/sonner/dist/index.mjs", import.meta.url),
      "utf8",
    );
    const appel = source.match(/^__insertCSS\((".*")\);?\s*$/m);
    expect(appel, "sonner n'injecte plus son CSS via __insertCSS").toBeTruthy();
    return JSON.parse(appel![1]);
  }

  function hash(contenu: string): string {
    return `'sha256-${createHash("sha256").update(contenu, "utf8").digest("base64")}'`;
  }

  it("épingle le <style> vide puis le <style> rempli, les deux temps de l'injection", () => {
    // `sonner` crée le `<style>`, l'attache vide, *puis* y met le CSS : le
    // navigateur évalue les deux états et rapporte donc deux hashes.
    const styleSrc = directive(buildCspPolicy("abc", { dev: false }), "style-src")!;

    expect(styleSrc).toContain(hash(""));
    expect(styleSrc).toContain(hash(cssInjecteParSonner()));
  });

  it("garde le nonce sur style-src, que les hashes ne remplacent pas", () => {
    // Les hashes n'autorisent que ces deux `<style>` précis ; tout le reste du
    // style en ligne reste soumis au nonce.
    expect(directive(buildCspPolicy("abc", { dev: false }), "style-src")).toContain(
      "'nonce-abc'",
    );
  });
});

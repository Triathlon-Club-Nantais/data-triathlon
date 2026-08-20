// @vitest-environment node
import { describe, expect, it } from "vitest";
import nextConfig from "./next.config";

/**
 * En-têtes de sécurité du front (#396, constat A05-2).
 *
 * Vercel pose déjà HSTS et `x-robots-tag` ; ce qui manquait tenait entièrement à
 * `headers()`. La CSP n'est pas ici : elle demande un `nonce` pour Next.js et
 * PostHog, et se traite à part.
 */
async function enTetes(): Promise<Map<string, string>> {
  const regles = await nextConfig.headers!();
  const attrapeTout = regles.find((regle) => regle.source === "/:path*");
  if (!attrapeTout) throw new Error("aucune règle attrape-tout dans headers()");
  return new Map(attrapeTout.headers.map(({ key, value }) => [key, value]));
}

describe("headers()", () => {
  it("interdit l'encadrement de toute page dans une iframe", async () => {
    expect((await enTetes()).get("X-Frame-Options")).toBe("DENY");
  });

  it("ferme la déduction de type de contenu", async () => {
    expect((await enTetes()).get("X-Content-Type-Options")).toBe("nosniff");
  });

  it("retient le référent complet sur les origines tierces", async () => {
    expect((await enTetes()).get("Referrer-Policy")).toBe("strict-origin-when-cross-origin");
  });

  it("refuse par défaut les API matérielles dont l'app ne se sert pas", async () => {
    const politique = (await enTetes()).get("Permissions-Policy");
    for (const fonctionnalite of ["camera", "microphone", "geolocation", "payment", "usb"]) {
      expect(politique).toContain(`${fonctionnalite}=()`);
    }
  });

  it("ne porte aucune directive CSP, qui vit entière dans proxy.ts", async () => {
    // #448 — deux en-têtes CSP sur une même réponse **se cumulent par
    // intersection**, chacun évalué séparément : scinder la politique donnerait
    // deux sources de vérité et des rapports en double. Le nonce, lui, ne peut
    // de toute façon pas venir d'ici : `headers()` ne sert que des constantes.
    for (const nom of (await enTetes()).keys()) {
      expect(nom.toLowerCase()).not.toContain("content-security-policy");
    }
  });
});

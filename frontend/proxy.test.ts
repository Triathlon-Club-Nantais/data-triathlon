import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";
import { proxy } from "./proxy";

function requeteAvec(cookies: Record<string, string>) {
  const requete = new NextRequest("https://exemple.fr/dashboard");
  for (const [nom, valeur] of Object.entries(cookies)) {
    requete.cookies.set(nom, valeur);
  }
  return requete;
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

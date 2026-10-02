/**
 * Chemin de retour après la saisie du code d'accès (`/acces?retour=…`, #877).
 *
 * Seul un chemin **interne** est rendu : un `retour` pris tel quel ferait de
 * `/acces` une redirection ouverte vers n'importe quel site (`//evil.example`,
 * `/\evil.example`, ou `/\t/evil.example`, dont le parseur d'URL retire la
 * tabulation). On résout donc le chemin comme le fera le routeur, et on refuse
 * tout ce qui sort de l'origine.
 */
const ORIGINE_FICTIVE = "http://origine.invalid";

export function cheminDeRetour(brut: string | undefined | null): string | null {
  if (!brut || !brut.startsWith("/")) {
    return null;
  }
  let url: URL;
  try {
    url = new URL(brut, ORIGINE_FICTIVE);
  } catch {
    return null;
  }
  if (url.origin !== ORIGINE_FICTIVE) {
    return null;
  }
  return url.pathname + url.search + url.hash;
}

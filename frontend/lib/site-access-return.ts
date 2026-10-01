/**
 * Chemin de retour après la saisie du code d'accès (`/acces?retour=…`, #877).
 *
 * Seul un chemin **interne** est rendu : un `retour` pris tel quel ferait de
 * `/acces` une redirection ouverte vers n'importe quel site (`//evil.example`,
 * `/\evil.example` que les navigateurs lisent comme un hôte).
 */
export function cheminDeRetour(brut: string | undefined | null): string | null {
  if (!brut || !brut.startsWith("/") || brut.startsWith("//") || brut.startsWith("/\\")) {
    return null;
  }
  return brut;
}

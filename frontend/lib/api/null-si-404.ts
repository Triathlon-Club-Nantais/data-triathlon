import { ApiError } from "./client";

/**
 * Convertit une ressource absente en `null`, et **laisse remonter le reste**.
 *
 * Avaler toute erreur ferait afficher « introuvable » sur un backend en panne ou
 * injoignable : indiscernable d'un lien mort pour le visiteur, privé du
 * « Réessayer » de `app/error.tsx`, et invisible en supervision.
 */
export function rendreNullSi404(erreur: unknown): null {
  if (erreur instanceof ApiError && erreur.status === 404) return null;
  throw erreur;
}

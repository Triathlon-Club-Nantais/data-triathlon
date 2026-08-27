/**
 * Couleurs du favicon selon l'environnement de déploiement (#665).
 *
 * `VERCEL_ENV` vaut `production` sur les deux projets Vercel (`data-triathlon`
 * et `data-triathlon-preview` déploient tous deux en `--prod`, cf.
 * `docs/ci-cd.md`) : inutilisable pour distinguer prod et preview. On reprend
 * le patron déjà en place pour les variables PostHog — une variable posée
 * uniquement sur `data-triathlon-preview`, absente ailleurs (prod, local).
 */

export const FAVICON_COLOR_PROD = "#e95d0f";
export const FAVICON_COLOR_PREVIEW = "#7c3aed";

export function getFaviconColor(variant: string | undefined): string {
  return variant === "preview" ? FAVICON_COLOR_PREVIEW : FAVICON_COLOR_PROD;
}

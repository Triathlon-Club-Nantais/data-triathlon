import posthog from "posthog-js";

/**
 * `posthog.capture()` appelé sans `posthog.init()` (token/host absents, cf.
 * instrumentation-client.ts) ne plante pas mais loggue un `console.error`
 * PostHog interne à chaque appel — bruit inutile sur un environnement où les
 * variables d'env manquent (preview mal configurée, etc.). Un seul point de
 * garde ici plutôt qu'un `if` répété à chacun des sites d'appel.
 */
export function captureEvent(...args: Parameters<typeof posthog.capture>) {
  if (!process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN) return;
  posthog.capture(...args);
}

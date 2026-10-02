import posthog from "posthog-js";

/**
 * PostHog n'est initialisé (`instrumentation-client.ts`) qu'avec token **et**
 * hôte : seule la production les porte. Tout appel à PostHog passe par cette
 * garde, sans quoi un réglage partiel appellerait une instance jamais démarrée.
 */
export function isPostHogEnabled(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN && process.env.NEXT_PUBLIC_POSTHOG_HOST);
}

/**
 * `posthog.capture()` appelé sans `posthog.init()` ne plante pas mais loggue un
 * `console.error` PostHog interne à chaque appel : un seul point de garde ici
 * plutôt qu'un `if` répété à chacun des sites d'appel.
 */
export function captureEvent(...args: Parameters<typeof posthog.capture>) {
  if (!isPostHogEnabled()) return;
  posthog.capture(...args);
}

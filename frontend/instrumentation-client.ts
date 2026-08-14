import posthog from "posthog-js";

const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN;
const host = process.env.NEXT_PUBLIC_POSTHOG_HOST;

if (!token || !host) {
  // Volontairement inconditionnel (pas de garde NODE_ENV) : ne rejoint que la
  // console devtools, jamais l'UI, mais une preview/prod mal configurée doit
  // rester détectable — un log dev-only serait silencieux exactement là où
  // ça compte (cf. revue #339).
  const missing = !token
    ? "NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN"
    : "NEXT_PUBLIC_POSTHOG_HOST";
  console.error(
    `Variable ${missing} requise par PostHog absente ou mal configurée, ` +
      `les événements sont silencieusement perdus. ` +
      `Cette erreur disparaît une fois ${missing} configurée.`,
  );
} else {
  posthog.init(token, {
    api_host: "/ingest",
    ui_host: host,
    // Option requise par PostHog
    defaults: "2026-01-30",
    // Capture les exceptions non gérées (Error Tracking)
    capture_exceptions: true,
    // Debug activé en développement seulement
    debug: process.env.NODE_ENV === "development",
  });
}

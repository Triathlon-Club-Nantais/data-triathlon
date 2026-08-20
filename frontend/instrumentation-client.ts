import posthog from "posthog-js";

const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN;
const host = process.env.NEXT_PUBLIC_POSTHOG_HOST;

// Analytics opt-in, et aucun avertissement quand les variables manquent : la
// **preview n'envoie rien à PostHog**, par choix (un seul projet PostHog, on
// n'y mélange pas le trafic de test — #426). L'absence de variable y est donc
// le réglage attendu, pas une erreur, et le `console.error` inconditionnel posé
// par la revue #339 n'y criait que du bruit. Reste le local, où ces variables
// sont vides par défaut (`.env.local.example`). Seule la production les porte :
// une prod mal configurée se voit dans PostHog, où les événements cesseraient
// d'arriver.
if (token && host) {
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

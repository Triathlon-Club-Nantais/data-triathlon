import { syncConsentCookie } from "@/lib/analytics-consent";
import { withPostHog } from "@/lib/posthog";

// Analytics opt-in, et aucun avertissement quand les variables manquent : la
// **preview n'envoie rien à PostHog**, par choix (un seul projet PostHog, on
// n'y mélange pas le trafic de test — #426). L'absence de variable y est donc
// le réglage attendu, pas une erreur, et le `console.error` inconditionnel posé
// par la revue #339 n'y criait que du bruit. Reste le local, où ces variables
// sont vides par défaut (`.env.local.example`). Seule la production les porte :
// une prod mal configurée se voit dans PostHog, où les événements cesseraient
// d'arriver.
syncConsentCookie();

// posthog-js se charge au repos du navigateur, après l'hydratation, plutôt que dans le JS initial
// de chaque page (#1394). Le délai borne l'attente sur une page qui ne se repose jamais. Un
// `captureEvent` émis plus tôt déclenche le chargement lui-même. Prix accepté : une exception levée
// avant l'init (hydratation comprise) échappe à Error Tracking, et une visite partie avant elle
// ne compte pas de page vue. Les web vitals, lus en `buffered`, ne perdent rien.
const start = () => withPostHog(() => {});
if ("requestIdleCallback" in window) requestIdleCallback(start, { timeout: 3000 });
else setTimeout(start, 0);

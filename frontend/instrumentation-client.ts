import posthog, { type CaptureResult } from "posthog-js";
import { readConsent } from "@/lib/analytics-consent";

const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN;
const host = process.env.NEXT_PUBLIC_POSTHOG_HOST;

// Écrans jeunes (#1307) : un événement lié à un élément ($autocapture, $rageclick, $dead_click,
// $dead_swipe...) emporte son texte, donc le nom d'un mineur ; une copie ou une erreur aussi. Le
// tri se fait sur la forme de l'événement, pas sur son nom, pour couvrir les événements qu'une
// version future de posthog-js ajoutera. Filtré au seul point de sortie : tout écran futur sous ce
// chemin est couvert, comme les dialogues en portail qu'un `ph-no-capture` ne couvrirait pas.
const YOUTH_PATH = /^\/admin\/jeunes(\/|$)/;
const ELEMENT_PROPERTIES = ["$elements", "$elements_chain", "$el_text"];
const TEXT_EVENTS = new Set(["$copy_autocapture", "$exception"]);

function leaksYouthData(event: CaptureResult): boolean {
  if (!YOUTH_PATH.test(window.location.pathname)) return false;
  return TEXT_EVENTS.has(event.event) || ELEMENT_PROPERTIES.some((key) => key in (event.properties ?? {}));
}

// Analytics opt-in, et aucun avertissement quand les variables manquent : la
// **preview n'envoie rien à PostHog**, par choix (un seul projet PostHog, on
// n'y mélange pas le trafic de test — #426). L'absence de variable y est donc
// le réglage attendu, pas une erreur, et le `console.error` inconditionnel posé
// par la revue #339 n'y criait que du bruit. Reste le local, où ces variables
// sont vides par défaut (`.env.local.example`). Seule la production les porte :
// une prod mal configurée se voit dans PostHog, où les événements cesseraient
// d'arriver.
if (token && host) {
  const granted = readConsent() === "granted";
  posthog.init(token, {
    api_host: "/ingest",
    ui_host: host,
    // Option requise par PostHog
    defaults: "2026-01-30",
    // Sans accord (#1159) : mesure sans cookie ni stockage, identité hachée côté PostHog, exemptée de
    // consentement par la CNIL. Exige le mode sans cookie activé dans les réglages du projet PostHog.
    cookieless_mode: "on_reject",
    opt_out_capturing_by_default: true,
    // L'autocapture des clics n'est ouverte qu'à l'accord ; un accord donné en cours de visite la
    // démarre au chargement suivant.
    autocapture: granted,
    // Fixés ici plutôt que laissés aux réglages distants du projet : sans accord, ni coordonnées de
    // clics ni clics morts ne partent.
    capture_heatmaps: granted,
    capture_dead_clicks: granted,
    before_send: (event) => (event && leaksYouthData(event) ? null : event),
    disable_session_recording: true,
    // Capture les exceptions non gérées (Error Tracking)
    capture_exceptions: true,
    // Debug activé en développement seulement
    debug: process.env.NODE_ENV === "development",
  });
  if (granted) {
    posthog.opt_in_capturing({ captureEventName: false });
  } else if (posthog.get_explicit_consent_status() === "granted") {
    // Accord PostHog que le choix du site ne couvre plus (six mois écoulés, stockage effacé).
    posthog.reset();
    posthog.opt_out_capturing();
  }
}

import type { CaptureResult, PostHog } from "posthog-js";
import { readConsent } from "@/lib/analytics-consent";

/**
 * PostHog n'est initialisé qu'avec token **et** hôte : seule la production les
 * porte. Tout appel à PostHog passe par cette garde, sans quoi un réglage
 * partiel appellerait une instance jamais démarrée.
 */
export function isPostHogEnabled(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN && process.env.NEXT_PUBLIC_POSTHOG_HOST);
}

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

// Query string et fragment (#1530) : `ResultsFilters` y pousse `name=`, `RaceFinishers` `q=`. Tri
// sur le nom de la clé, à toute profondeur, pour couvrir `$current_url`, `$referrer`, leurs copies
// `$initial_*` et `$session_entry_*`, `$external_click_url`, et les `navigationURL` et
// `attribution.url` des web vitals, le `attr__href` d'un lien cliqué et les fichiers d'une trace
// d'exception. `$elements_chain` et les cartes de chaleur portent l'URL ailleurs que dans une valeur.
const URL_KEY = /(url|referrer|href|filename|abs_path)$/i;

// Coupe aussi les liens relatifs (`/resultats?name=…`) ; laisse "$direct" intact.
const withoutQuery = (value: string) => value.split(/[?#]/, 1)[0];

function stripUrls(value: unknown, key = ""): unknown {
  if (key === "$elements_chain" && typeof value === "string") {
    return value.replace(/href="([^"?#]*)[^"]*"/g, 'href="$1"');
  }
  if (typeof value === "string") return URL_KEY.test(key) ? withoutQuery(value) : value;
  if (Array.isArray(value)) return value.map((item) => stripUrls(item, key));
  // Objets simples seuls : un `Date` (timestamp) ne se parcourt pas, `undefined` non plus.
  if (value === null || typeof value !== "object" || Object.getPrototypeOf(value) !== Object.prototype) return value;
  if (key === "$heatmap_data") {
    const byUrl: Record<string, unknown[]> = {};
    for (const [url, points] of Object.entries(value as Record<string, unknown[]>)) {
      (byUrl[withoutQuery(url)] ??= []).push(...points);
    }
    return byUrl;
  }
  return Object.fromEntries(Object.entries(value as object).map(([k, v]) => [k, stripUrls(v, k)]));
}

function init(posthog: PostHog): void {
  const granted = readConsent() === "granted";
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN!, {
    api_host: "/ingest",
    ui_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
    // Option requise par PostHog
    defaults: "2026-01-30",
    // Sans accord (#1159) : mesure sans cookie ni stockage, identité hachée côté PostHog, exemptée de
    // consentement par la CNIL. Exige le mode sans cookie activé dans les réglages du projet PostHog.
    cookieless_mode: "on_reject",
    opt_out_capturing_by_default: true,
    // L'autocapture des clics n'est ouverte qu'à l'accord ; un accord donné après l'init la
    // démarre au chargement suivant.
    autocapture: granted,
    // Fixés ici plutôt que laissés aux réglages distants du projet : sans accord, ni coordonnées de
    // clics ni clics morts ne partent.
    capture_heatmaps: granted,
    capture_dead_clicks: granted,
    before_send: (event) => (!event || leaksYouthData(event) ? null : (stripUrls(event) as CaptureResult)),
    disable_session_recording: true,
    // Core Web Vitals (LCP, INP, CLS) fixés ici plutôt que laissés aux réglages distants (#1318).
    // Envoyés aussi en mode sans cookie, sans identifiant de session client.
    capture_performance: { web_vitals: true },
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

// posthog-js pèse ~100 Ko gzip : chargé à part, jamais dans le JS initial des pages (#1394).
let instance: PostHog | null = null;
let loading: Promise<PostHog> | null = null;

function load(): Promise<PostHog> {
  loading ??= import("posthog-js").then(({ default: posthog }) => {
    init(posthog);
    instance = posthog;
    return posthog;
  });
  return loading;
}

/**
 * Seul accès à PostHog. Sans variables, rien n'est téléchargé. Avant la fin du
 * chargement, l'appel attend l'init, dans l'ordre d'émission ; après, il est
 * synchrone, ce que `login_initiated` exige (sendBeacon avant la navigation).
 */
export function withPostHog(call: (posthog: PostHog) => void): void {
  if (!isPostHogEnabled()) return;
  if (instance) call(instance);
  // Un échec de chargement (réseau, bloqueur) coupe la mesure, jamais la page.
  else load().then(call, () => {});
}

/**
 * `posthog.capture()` sans `posthog.init()` loggue un `console.error` PostHog
 * interne à chaque appel : la garde de `withPostHog` l'évite à chacun des
 * sites d'appel.
 */
export function captureEvent(...args: Parameters<PostHog["capture"]>) {
  withPostHog((posthog) => posthog.capture(...args));
}

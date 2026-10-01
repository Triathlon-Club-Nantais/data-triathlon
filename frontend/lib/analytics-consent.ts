import posthog from "posthog-js";
import { useSyncExternalStore } from "react";

/**
 * Choix du visiteur sur la mesure d'audience détaillée (#1159).
 *
 * Sans accord, PostHog tourne en mode sans cookie (`cookieless_mode:
 * "on_reject"`, `instrumentation-client.ts`) : une mesure statistique exemptée
 * de consentement par la CNIL. L'accord ouvre les cookies, l'autocapture des
 * clics et le rattachement au compte (`identify`). Le choix vaut six mois, durée
 * recommandée par la CNIL avant de redemander.
 */
export type AnalyticsConsent = "granted" | "denied" | "pending";

export const ANALYTICS_CONSENT_KEY = "tcn-analytics-consent";
export const CONSENT_VALIDITY_DAYS = 182;
const CHANGED_EVENT = "tcn-analytics-consent-changed";
const DAY_MS = 24 * 60 * 60 * 1000;

export function readConsent(): AnalyticsConsent {
  if (typeof window === "undefined") return "pending";
  try {
    const stored = JSON.parse(localStorage.getItem(ANALYTICS_CONSENT_KEY) ?? "null");
    if (stored?.choice !== "granted" && stored?.choice !== "denied") return "pending";
    if (Date.now() - Number(stored.at) > CONSENT_VALIDITY_DAYS * DAY_MS) return "pending";
    return stored.choice;
  } catch {
    return "pending";
  }
}

export function saveConsent(choice: "granted" | "denied"): void {
  localStorage.setItem(ANALYTICS_CONSENT_KEY, JSON.stringify({ choice, at: Date.now() }));
  if (process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN) {
    if (choice === "granted") {
      posthog.opt_in_capturing({ captureEventName: false });
    } else {
      // `reset()` avant l'opt-out, jamais après un opt-in : il efface les traceurs déjà posés.
      posthog.reset();
      posthog.opt_out_capturing();
    }
  }
  window.dispatchEvent(new Event(CHANGED_EVENT));
}

function subscribe(onChange: () => void) {
  window.addEventListener(CHANGED_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGED_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** `"pending"` au rendu serveur : le choix ne vit que dans le navigateur. */
export function useAnalyticsConsent(): AnalyticsConsent {
  return useSyncExternalStore(subscribe, readConsent, () => "pending");
}

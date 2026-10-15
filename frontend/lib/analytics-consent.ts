"use client";
import { useSyncExternalStore } from "react";
import { ANALYTICS_CONSENT_COOKIE, ANALYTICS_CONSENT_KEY } from "@/lib/constants";
import { withPostHog } from "@/lib/posthog";

/**
 * Choix du visiteur sur la mesure d'audience détaillée (#1159).
 *
 * Sans accord, PostHog tourne en mode sans cookie (`cookieless_mode:
 * "on_reject"`, `lib/posthog.ts`) : une mesure statistique exemptée
 * de consentement par la CNIL. L'accord ouvre les cookies, l'autocapture des
 * clics et le rattachement au compte (`identify`). Le choix vaut six mois, durée
 * recommandée par la CNIL avant de redemander.
 */
export type AnalyticsConsent = "granted" | "denied" | "pending";

export { ANALYTICS_CONSENT_COOKIE, ANALYTICS_CONSENT_KEY };
export const CONSENT_VALIDITY_DAYS = 182;
const CHANGED_EVENT = "tcn-analytics-consent-changed";
const DAY_MS = 24 * 60 * 60 * 1000;

// Repli quand le navigateur refuse l'écriture (stockage plein ou bloqué) : le choix vaut pour la visite.
let unsavedChoice: "granted" | "denied" | null = null;

function storedChoice(): { choice: "granted" | "denied"; expiresAt: number } | null {
  try {
    const stored = JSON.parse(localStorage.getItem(ANALYTICS_CONSENT_KEY) ?? "null");
    if (stored?.choice !== "granted" && stored?.choice !== "denied") return null;
    const expiresAt = Number(stored.at) + CONSENT_VALIDITY_DAYS * DAY_MS;
    return Date.now() > expiresAt ? null : { choice: stored.choice, expiresAt };
  } catch {
    return null;
  }
}

export function readConsent(): AnalyticsConsent {
  if (typeof window === "undefined") return "pending";
  return unsavedChoice ?? storedChoice()?.choice ?? "pending";
}

/**
 * Recopie l'accord dans un cookie pour le serveur, qui ne lit pas `localStorage` (#1359). Appelé à
 * chaque choix et au chargement. Le cookie expire avec l'accord, pas six mois après la dernière
 * visite : le retour de connexion atteint le serveur avant que cette fonction ait pu le retirer.
 */
export function syncConsentCookie(): void {
  const attributes = `Path=/; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  const stored = storedChoice();
  if (unsavedChoice === "granted") {
    // Choix non enregistré : il ne vaut que pour la visite, cookie de session.
    document.cookie = `${ANALYTICS_CONSENT_COOKIE}=granted; ${attributes}`;
  } else if (!unsavedChoice && stored?.choice === "granted") {
    const maxAge = Math.ceil((stored.expiresAt - Date.now()) / 1000);
    document.cookie = `${ANALYTICS_CONSENT_COOKIE}=granted; Max-Age=${maxAge}; ${attributes}`;
  } else {
    document.cookie = `${ANALYTICS_CONSENT_COOKIE}=; Max-Age=0; ${attributes}`;
  }
}

export function saveConsent(choice: "granted" | "denied"): void {
  try {
    localStorage.setItem(ANALYTICS_CONSENT_KEY, JSON.stringify({ choice, at: Date.now() }));
    unsavedChoice = null;
  } catch {
    unsavedChoice = choice;
  }
  syncConsentCookie();
  withPostHog((posthog) => {
    if (choice === "granted") {
      posthog.opt_in_capturing({ captureEventName: false });
    } else {
      // `reset()` avant l'opt-out, jamais après un opt-in : il efface les traceurs déjà posés.
      posthog.reset();
      posthog.opt_out_capturing();
    }
  });
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

/** `"pending"` au rendu serveur : le choix ne se lit qu'au navigateur. */
export function useAnalyticsConsent(): AnalyticsConsent {
  return useSyncExternalStore(subscribe, readConsent, () => "pending");
}

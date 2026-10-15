import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { optIn, optOut, reset } = vi.hoisted(() => ({ optIn: vi.fn(), optOut: vi.fn(), reset: vi.fn() }));
vi.mock("posthog-js", () => ({
  default: { init: vi.fn(), get_explicit_consent_status: vi.fn(), opt_in_capturing: optIn, opt_out_capturing: optOut, reset },
}));

import {
  ANALYTICS_CONSENT_COOKIE,
  ANALYTICS_CONSENT_KEY,
  CONSENT_VALIDITY_DAYS,
  readConsent,
  saveConsent,
  syncConsentCookie,
} from "./analytics-consent";

describe("Consentement à la mesure d'audience détaillée (#1159)", () => {
  beforeEach(() => {
    localStorage.clear();
    optIn.mockClear();
    optOut.mockClear();
    reset.mockClear();
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  it("est en attente tant qu'aucun choix n'a été fait", () => {
    expect(readConsent()).toBe("pending");
  });

  it("mémorise l'accord et active le suivi détaillé", async () => {
    saveConsent("granted");
    expect(readConsent()).toBe("granted");
    await vi.waitFor(() => expect(optIn).toHaveBeenCalledWith({ captureEventName: false }));
  });

  it("mémorise le refus et repasse en mesure sans cookie, traceurs effacés", async () => {
    saveConsent("granted");
    saveConsent("denied");
    expect(readConsent()).toBe("denied");
    await vi.waitFor(() => expect(optOut).toHaveBeenCalled());
    expect(reset).toHaveBeenCalled();
  });

  it("redemande le choix au bout de six mois", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 0, 1));
    saveConsent("denied");
    vi.setSystemTime(new Date(2026, 0, 1 + CONSENT_VALIDITY_DAYS + 1));
    expect(readConsent()).toBe("pending");
  });

  it("traite un stockage illisible comme une absence de choix", () => {
    localStorage.setItem(ANALYTICS_CONSENT_KEY, "{pas du json");
    expect(readConsent()).toBe("pending");
  });

  it("applique le choix pour la visite quand le navigateur refuse de l'enregistrer", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    try {
      saveConsent("denied");
      expect(readConsent()).toBe("denied");
      await vi.waitFor(() => expect(optOut).toHaveBeenCalled());
    } finally {
      setItem.mockRestore();
    }
    saveConsent("granted");
    expect(readConsent()).toBe("granted");
  });

  it("transmet l'accord au serveur par un cookie technique, retiré au refus (#1359)", () => {
    saveConsent("granted");
    expect(document.cookie).toContain(`${ANALYTICS_CONSENT_COOKIE}=granted`);
    saveConsent("denied");
    expect(document.cookie).not.toContain(ANALYTICS_CONSENT_COOKIE);
  });

  it("fait expirer le cookie avec l'accord, pas six mois après la dernière visite", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 0, 1));
    saveConsent("granted");
    vi.advanceTimersByTime((CONSENT_VALIDITY_DAYS - 1) * 24 * 60 * 60 * 1000);
    const write = vi.spyOn(Document.prototype, "cookie", "set");
    try {
      syncConsentCookie();
      expect(write).toHaveBeenCalledWith(expect.stringContaining(`Max-Age=${24 * 60 * 60};`));
    } finally {
      write.mockRestore();
    }
  });

  it("aligne le cookie sur le choix mémorisé au chargement, expiration comprise", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 0, 1));
    localStorage.setItem(ANALYTICS_CONSENT_KEY, JSON.stringify({ choice: "granted", at: Date.now() }));
    syncConsentCookie();
    expect(document.cookie).toContain(`${ANALYTICS_CONSENT_COOKIE}=granted`);
    vi.setSystemTime(new Date(2026, 0, 1 + CONSENT_VALIDITY_DAYS + 1));
    syncConsentCookie();
    expect(document.cookie).not.toContain(ANALYTICS_CONSENT_COOKIE);
  });

  it("ne touche pas à PostHog quand il n'est pas configuré", async () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "");
    saveConsent("granted");
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(optIn).not.toHaveBeenCalled();
  });
});

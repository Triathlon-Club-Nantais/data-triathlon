import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { optIn, optOut, reset } = vi.hoisted(() => ({ optIn: vi.fn(), optOut: vi.fn(), reset: vi.fn() }));
vi.mock("posthog-js", () => ({
  default: { opt_in_capturing: optIn, opt_out_capturing: optOut, reset },
}));

import { ANALYTICS_CONSENT_KEY, CONSENT_VALIDITY_DAYS, readConsent, saveConsent } from "./analytics-consent";

describe("Consentement à la mesure d'audience détaillée (#1159)", () => {
  beforeEach(() => {
    localStorage.clear();
    optIn.mockClear();
    optOut.mockClear();
    reset.mockClear();
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
  });

  it("est en attente tant qu'aucun choix n'a été fait", () => {
    expect(readConsent()).toBe("pending");
  });

  it("mémorise l'accord et active le suivi détaillé", () => {
    saveConsent("granted");
    expect(readConsent()).toBe("granted");
    expect(optIn).toHaveBeenCalledWith({ captureEventName: false });
  });

  it("mémorise le refus et repasse en mesure sans cookie, traceurs effacés", () => {
    saveConsent("granted");
    saveConsent("denied");
    expect(readConsent()).toBe("denied");
    expect(reset).toHaveBeenCalled();
    expect(optOut).toHaveBeenCalled();
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

  it("ne touche pas à PostHog quand il n'est pas configuré", () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "");
    saveConsent("granted");
    expect(optIn).not.toHaveBeenCalled();
  });
});

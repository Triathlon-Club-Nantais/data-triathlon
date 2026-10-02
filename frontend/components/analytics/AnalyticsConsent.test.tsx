import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("posthog-js", () => ({
  default: { opt_in_capturing: vi.fn(), opt_out_capturing: vi.fn(), reset: vi.fn() },
}));

import { AnalyticsConsentBanner, AnalyticsConsentSettings } from "./AnalyticsConsent";
import { readConsent } from "@/lib/analytics-consent";

beforeEach(() => {
  localStorage.clear();
  vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "test-token");
  vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "https://eu.posthog.com");
});

describe("AnalyticsConsentBanner (#1159)", () => {
  it("demande le choix tant qu'il n'a pas été fait, refus et accord au même niveau", () => {
    render(<AnalyticsConsentBanner />);
    const bandeau = screen.getByRole("region", { name: "Mesure d'audience" });
    expect(bandeau).toHaveTextContent(/sans cookie/);
    const refuser = screen.getByRole("button", { name: "Refuser" });
    const accepter = screen.getByRole("button", { name: "Accepter" });
    expect(refuser.className).toBe(accepter.className);
    expect(screen.getByRole("link", { name: "En savoir plus" })).toHaveAttribute("href", "/confidentialite#cookies");
  });

  it("enregistre le refus et disparaît", async () => {
    render(<AnalyticsConsentBanner />);
    await userEvent.click(screen.getByRole("button", { name: "Refuser" }));
    expect(readConsent()).toBe("denied");
    expect(screen.queryByRole("region", { name: "Mesure d'audience" })).not.toBeInTheDocument();
  });

  it("enregistre l'accord et disparaît", async () => {
    render(<AnalyticsConsentBanner />);
    await userEvent.click(screen.getByRole("button", { name: "Accepter" }));
    expect(readConsent()).toBe("granted");
    expect(screen.queryByRole("region", { name: "Mesure d'audience" })).not.toBeInTheDocument();
  });

  it("ne s'affiche pas quand PostHog n'est pas configuré (local, preview)", () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN", "");
    render(<AnalyticsConsentBanner />);
    expect(screen.queryByRole("region", { name: "Mesure d'audience" })).not.toBeInTheDocument();
  });
});

describe("AnalyticsConsentSettings (#1159)", () => {
  it("dit que la mesure est inactive là où PostHog ne tourne pas", () => {
    vi.stubEnv("NEXT_PUBLIC_POSTHOG_HOST", "");
    render(<AnalyticsConsentSettings />);
    expect(screen.getByText(/pas active/i)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("dit le choix en cours et permet d'en changer à tout moment", async () => {
    render(<AnalyticsConsentSettings />);
    expect(screen.getByText(/vous n'avez pas encore fait de choix/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Accepter la mesure détaillée" }));
    expect(screen.getByText(/vous avez accepté/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Refuser la mesure détaillée" }));
    expect(screen.getByText(/vous avez refusé/i)).toBeInTheDocument();
    expect(readConsent()).toBe("denied");
  });
});

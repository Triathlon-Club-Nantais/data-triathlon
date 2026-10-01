"use client";
import Link from "next/link";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/tcn/Button";
import { saveConsent, useAnalyticsConsent } from "@/lib/analytics-consent";

const noopSubscribe = () => () => {};

/** Faux au rendu serveur et à l'hydratation : le choix ne se lit qu'au navigateur, sans bandeau fantôme. */
function useHydrated() {
  return useSyncExternalStore(noopSubscribe, () => true, () => false);
}

/**
 * Demande d'accord à la mesure d'audience détaillée (#1159). Refuser et accepter
 * ont le même poids (exigence CNIL) ; ignorer le bandeau laisse la mesure sans
 * cookie, seule active par défaut.
 */
export function AnalyticsConsentBanner() {
  const consent = useAnalyticsConsent();
  const hydrated = useHydrated();
  if (!process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN || !hydrated || consent !== "pending") return null;

  return (
    <section
      aria-label="Mesure d'audience"
      // Au-dessus de la barre basse sous md, comme le bouton de signalement.
      className="fixed inset-x-3 bottom-[calc(12px+var(--tcn-nav-bottom))] z-50 mx-auto max-w-xl md:bottom-6"
      style={{
        background: "var(--tcn-surface)",
        border: "1px solid var(--tcn-border)",
        borderRadius: "var(--tcn-radius-2xl)",
        boxShadow: "var(--tcn-shadow-pop)",
        padding: "var(--tcn-space-5)",
      }}
    >
      <p className="text-sm text-foreground">
        Ce site mesure sa fréquentation sans cookie et sans vous suivre individuellement. Acceptez-vous une mesure
        détaillée (cookies, clics, et rattachement à votre compte si vous êtes connecté au back-office) pour aider
        les bénévoles à l&apos;améliorer ?{" "}
        <Link
          href="/confidentialite#cookies"
          prefetch={false}
          className="font-medium text-[var(--tcn-orange-deep)] underline underline-offset-2"
        >
          En savoir plus
        </Link>
      </p>
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={() => saveConsent("denied")}>
          Refuser
        </Button>
        <Button variant="secondary" size="sm" onClick={() => saveConsent("granted")}>
          Accepter
        </Button>
      </div>
    </section>
  );
}

const STATUS = {
  granted: "Vous avez accepté la mesure détaillée.",
  denied: "Vous avez refusé la mesure détaillée : seule la mesure sans cookie est active.",
  pending: "Vous n'avez pas encore fait de choix : seule la mesure sans cookie est active.",
} as const;

/** Retirer ou donner son accord à tout moment, depuis la politique de confidentialité. */
export function AnalyticsConsentSettings() {
  const consent = useAnalyticsConsent();
  return (
    <div className="space-y-2">
      <p aria-live="polite">{STATUS[consent]}</p>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          aria-pressed={consent === "granted"}
          onClick={() => saveConsent("granted")}
        >
          Accepter la mesure détaillée
        </Button>
        <Button variant="secondary" size="sm" aria-pressed={consent === "denied"} onClick={() => saveConsent("denied")}>
          Refuser la mesure détaillée
        </Button>
      </div>
    </div>
  );
}

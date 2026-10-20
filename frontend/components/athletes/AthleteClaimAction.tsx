"use client";

import Link from "next/link";
import { Alert, Button, MetaPill } from "@/components/tcn";
import { nomComplet } from "@/components/layout/AthletePicker";
import { useRequestAthleteClaim } from "@/lib/queries/auth";
import type { ClaimedAthlete, SessionUser } from "@/lib/types";

const EXPLICATION_ID = "rattacher-fiche-explication";
const texteDiscret = { margin: 0, fontSize: 13, lineHeight: 1.45, color: "var(--tcn-text-muted)" } as const;

/**
 * Coin « c'est moi » de la fiche pour un connecté (#1325). Jamais d'office : la
 * demande part dans la file du club, qui la valide ou la refuse.
 */
export function AthleteClaimAction({ athlete, session }: { athlete: ClaimedAthlete; session: SessionUser }) {
  const demander = useRequestAthleteClaim();
  const demande = session.athlete_claim;

  if (demande?.status === "pending" && demande.athlete.id === athlete.id) {
    return (
      <p role="status" style={{ ...texteDiscret, maxWidth: 300 }}>
        Demande de rattachement en attente : le club vérifie qu&apos;il s&apos;agit bien de vous.
      </p>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8, maxWidth: 300 }}>
      <Button
        variant="secondary"
        aria-describedby={EXPLICATION_ID}
        aria-disabled={demander.isPending || undefined}
        onClick={() => {
          if (!demander.isPending) demander.mutate(athlete.id);
        }}
      >
        C&apos;est moi
      </Button>
      <p id={EXPLICATION_ID} style={texteDiscret}>
        Rattacher cette fiche à votre compte. Le club valide la demande.
        {demande?.status === "pending" && ` Elle remplace votre demande pour ${nomComplet(demande.athlete)}.`}
        {demande?.status === "rejected" &&
          demande.athlete.id === athlete.id &&
          " Votre demande précédente pour cette fiche a été refusée."}
      </p>
      {demander.error && (
        <div role="alert">
          <Alert status="error" title="Demande non envoyée">
            {demander.error.message}
          </Alert>
        </div>
      )}
    </div>
  );
}

/** À la place de la sélection locale, pour un compte rattaché à une fiche. */
export function LinkedAthleteMark({ athlete, linked }: { athlete: ClaimedAthlete; linked: ClaimedAthlete }) {
  if (linked.id === athlete.id) {
    return (
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
        <MetaPill accent dot>
          Votre fiche
        </MetaPill>
        <Link href="/mon-compte" style={texteDiscret} className="inline-flex min-h-11 items-center underline underline-offset-2">
          Gérer ma fiche
        </Link>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
      <p style={texteDiscret}>
        Fiche de votre compte :{" "}
        <Link href={`/athletes/${linked.id}`} className="underline underline-offset-2">
          {nomComplet(linked)}
        </Link>
      </p>
      <Link
        href={`/athletes/${linked.id}?comparer=${athlete.id}`}
        aria-label={`Me comparer à ${nomComplet(athlete)}`}
        className="tcn-cible-tactile inline-flex items-center text-sm font-semibold text-accent-ink hover:underline"
      >
        Me comparer →
      </Link>
    </div>
  );
}

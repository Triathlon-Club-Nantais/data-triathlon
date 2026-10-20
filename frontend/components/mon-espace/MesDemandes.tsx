"use client";

import Link from "next/link";
import { useState } from "react";
import { nomComplet } from "@/components/layout/AthletePicker";
import { Alert, Button, Card, Eyebrow } from "@/components/tcn";
import { useCancelAthleteClaim, useCancelResultClaim, useHydratedSession, useMyResultClaims } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";

const STATUT = { pending: "En attente", rejected: "Refusée" } as const;

function Demande({
  titre,
  detail,
  status,
  nomAction,
  onCancel,
  isPending,
  error,
}: {
  titre: React.ReactNode;
  detail: string;
  status: keyof typeof STATUT;
  nomAction: string;
  onCancel: () => void;
  isPending: boolean;
  error: Error | null;
}) {
  const [confirmer, setConfirmer] = useState(false);
  return (
    <li style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
      {titre}
      <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>
        <strong style={{ fontWeight: 600 }}>{STATUT[status]}</strong>
        {detail && ` · ${detail}`}
      </span>
      {status === "pending" && (
        <Button
          variant="secondary"
          size="sm"
          aria-label={`${confirmer ? "Confirmer" : "Annuler la demande"} : ${nomAction}`}
          aria-disabled={isPending || undefined}
          onClick={() => {
            if (isPending) return;
            if (confirmer) onCancel();
            else setConfirmer(true);
          }}
        >
          {confirmer ? "Confirmer" : "Annuler la demande"}
        </Button>
      )}
      {error && (
        <div role="alert">
          <Alert status="error" title="Demande non annulée">
            {error.message}
          </Alert>
        </div>
      )}
    </li>
  );
}

/** Mes demandes en cours (#1670) : rattachement de fiche et réclamations de résultat, avec leur statut. */
export function MesDemandes() {
  const session = useHydratedSession();
  const fiche = session.data?.athlete ?? null;
  const rattachement = session.data?.athlete_claim ?? null;
  const reclamations = useMyResultClaims(fiche !== null).data ?? [];
  const annulerRattachement = useCancelAthleteClaim();
  const annulerReclamation = useCancelResultClaim();

  if (rattachement === null && reclamations.length === 0) return null;
  return (
    <Card padding={20}>
      <Eyebrow>
        <h2 style={{ margin: 0, font: "inherit", letterSpacing: "inherit", textTransform: "inherit" }}>Mes demandes</h2>
      </Eyebrow>
      <p style={{ margin: "8px 0 12px", fontSize: 13, color: "var(--tcn-text-muted)" }}>
        Une réclamation acceptée disparaît : le résultat est alors sur votre fiche.
      </p>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 16 }}>
        {rattachement !== null && (
          <Demande
            titre={<span style={{ fontSize: 15, fontWeight: 600 }}>Rattachement à la fiche de {nomComplet(rattachement.athlete)}</span>}
            detail={formatDate(rattachement.created_at)}
            status={rattachement.status}
            nomAction={`rattachement à la fiche de ${nomComplet(rattachement.athlete)}`}
            onCancel={() => annulerRattachement.mutate()}
            isPending={annulerRattachement.isPending}
            error={annulerRattachement.error}
          />
        )}
        {reclamations.map((c) => (
          <Demande
            key={c.id}
            titre={
              <Link href={`/courses/${c.course_id}`} className="tcn-cible-tactile underline underline-offset-2" style={{ fontSize: 15, fontWeight: 600 }}>
                {c.course_name}
              </Link>
            }
            detail={formatDate(c.event_date)}
            status={c.status}
            nomAction={c.course_name}
            onCancel={() => annulerReclamation.mutate(c.id)}
            isPending={annulerReclamation.isPending}
            error={annulerReclamation.variables === c.id ? annulerReclamation.error : null}
          />
        ))}
      </ul>
    </Card>
  );
}

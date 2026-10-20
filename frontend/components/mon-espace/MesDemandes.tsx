"use client";

import Link from "next/link";
import { useState } from "react";
import { Alert, Button, Card, Eyebrow } from "@/components/tcn";
import { useCancelResultClaim, useHydratedSession, useMyResultClaims } from "@/lib/queries/auth";
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
            {error.message} Réessayez avec « Confirmer ».
          </Alert>
        </div>
      )}
    </li>
  );
}

/** Mes réclamations de résultat en cours (#1670), avec leur statut. */
export function MesDemandes() {
  const session = useHydratedSession();
  const fiche = session.data?.athlete ?? null;
  const reclamations = useMyResultClaims(fiche !== null).data ?? [];
  const annulerReclamation = useCancelResultClaim();

  if (reclamations.length === 0) return null;
  return (
    <Card padding={20}>
      <Eyebrow>
        <h2 style={{ margin: 0, font: "inherit", letterSpacing: "inherit", textTransform: "inherit" }}>Mes demandes</h2>
      </Eyebrow>
      <p style={{ margin: "8px 0 12px", fontSize: 13, color: "var(--tcn-text-muted)" }}>
        Une demande acceptée disparaît : le résultat est alors sur votre fiche.
      </p>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 16 }}>
        {reclamations.map((c) => (
          <Demande
            key={c.id}
            titre={
              <Link href={`/courses/${c.course_id}`} className="tcn-cible-tactile break-words underline underline-offset-2" style={{ fontSize: 15, fontWeight: 600 }}>
                {c.course_name}
                {c.event_date && ` · ${formatDate(c.event_date)}`}
              </Link>
            }
            detail={`Demandée le ${formatDate(c.created_at)}`}
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

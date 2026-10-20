"use client";

import { Alert, Button } from "@/components/tcn";
import {
  useCancelResultClaim,
  useHydratedSession,
  useMyResultClaims,
  useRequestResultClaim,
} from "@/lib/queries/auth";
import type { Participation } from "@/lib/types";
import { estRelais } from "@/lib/utils/relais";

const EXPLICATION_ID = "reclamer-resultat-explication";
const texteDiscret = { margin: 0, fontSize: 13, lineHeight: 1.45, color: "var(--tcn-text-muted)" } as const;

/**
 * « Ce résultat est à moi » (#1637) : un compte rattaché réclame un résultat
 * rangé sur une autre fiche, celle d'un homonyme par exemple. Jamais d'office :
 * le club vérifie, puis déplace le résultat sur la fiche du compte. Sur un
 * relais (#1739), « Je faisais partie de cette équipe » : le club ajoute la
 * fiche du compte à l'équipe.
 */
export function ResultClaimAction({ participation }: { participation: Participation }) {
  const session = useHydratedSession();
  const fiche = session.data?.athlete ?? null;
  const relais = estRelais(participation);
  const eligible =
    fiche !== null &&
    participation.athlete.id !== fiche.id &&
    !participation.is_pending_validation &&
    !(participation.teammates ?? []).some((equipier) => equipier.id === fiche.id);
  const mine = useMyResultClaims(eligible);
  const demander = useRequestResultClaim();
  const annuler = useCancelResultClaim();

  if (!eligible || mine.isPending) return null;
  const claim = mine.data?.find((c) => c.participation_id === participation.id);
  const erreur = demander.error ?? annuler.error;

  if (claim?.status === "pending") {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6, maxWidth: 300 }}>
        <p role="status" style={texteDiscret}>
          Réclamation en attente : le club vérifie qu&apos;il s&apos;agit bien de vous.
        </p>
        <Button
          variant="secondary"
          size="sm"
          aria-disabled={annuler.isPending || undefined}
          onClick={() => {
            if (!annuler.isPending) annuler.mutate(claim.id);
          }}
        >
          Annuler la réclamation
        </Button>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8, maxWidth: 300 }}>
      <Button
        variant="secondary"
        aria-describedby={EXPLICATION_ID}
        aria-disabled={demander.isPending || undefined}
        onClick={() => {
          if (!demander.isPending) demander.mutate(participation.id);
        }}
      >
        {relais ? "Je faisais partie de cette équipe" : "Ce résultat est à moi"}
      </Button>
      <p id={EXPLICATION_ID} style={texteDiscret}>
        {relais
          ? "Le club vérifie puis ajoute votre fiche à l'équipe."
          : "Il est rangé sur une autre fiche : le club vérifie puis déplace ce résultat sur votre fiche."}
        {claim?.status === "rejected" && " Votre réclamation précédente a été refusée."}
      </p>
      {erreur && (
        <div role="alert">
          <Alert status="error" title="Réclamation non envoyée">
            {erreur.message}
          </Alert>
        </div>
      )}
    </div>
  );
}

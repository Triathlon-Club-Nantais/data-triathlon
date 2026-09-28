"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button, Card, SegmentedControl } from "@/components/tcn";
import { useSeasonQuota, useUnvalidateSeason, useValidateSeason } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import type { SeasonQuota } from "@/lib/types";
import { currentSeason, seasonLabel } from "@/lib/utils/season";

export type CoureurAValider = {
  id: number;
  nom: string;
  prenom: string;
};

const ECHEC_VALIDATION = "La saison n'a pas pu être validée. Réessayez dans un instant.";
const ECHEC_DEVALIDATION = "La saison n'a pas pu être dévalidée. Réessayez dans un instant.";
const ECHEC_LECTURE = "Le quota de saison n'a pas pu être lu. Réessayez dans un instant.";

/**
 * Actions d'administration du quota de saison d'un coureur (#709) — sur la
 * fiche publique, comme `AthleteAdminPanel`, invisible sans le pouvoir dédié
 * `athletes:season_validate` (FR-009). Le geste admin de déclaration de
 * bénévolat qui vivait ici a été retiré (#780) — le seul chemin restant est
 * le formulaire public self-service (#778).
 */
export function SeasonValidationPanel({ athlete }: { athlete: CoureurAValider }) {
  const session = useHydratedSession();
  const peutValiderSaison = session.data?.permissions.includes("athletes:season_validate") ?? false;
  // La saison précédente reste accessible : c'est elle qu'on clôture en
  // septembre, après la bascule du 1er (#956).
  const enCours = currentSeason();
  const [season, setSeason] = useState(enCours);
  const quota = useSeasonQuota(athlete.id, season, peutValiderSaison);

  if (!peutValiderSaison) return null;
  // Premier bloc de la fiche : une carte vide pendant la lecture ferait sauter
  // la page à son arrivée.
  if (!quota.data && !quota.isError) return null;

  return (
    <Card>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div role="group" aria-label="Saison à valider">
          <SegmentedControl
            options={[enCours, enCours - 1].map((annee) => ({
              value: String(annee),
              label: seasonLabel(annee),
            }))}
            value={String(season)}
            onChange={(valeur) => setSeason(Number(valeur))}
          />
        </div>
        {quota.data ? (
          <ValiderSaison
            athleteId={athlete.id}
            season={season}
            quota={quota.data}
            // L'ancien quota reste affiché pendant la lecture du nouveau : ses
            // boutons agiraient sur la saison choisie avec l'état de l'autre.
            enLecture={quota.isPlaceholderData}
          />
        ) : (
          <p style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>{ECHEC_LECTURE}</p>
        )}
      </div>
    </Card>
  );
}

function ValiderSaison({
  athleteId,
  season,
  quota,
  enLecture,
}: {
  athleteId: number;
  season: number;
  quota: SeasonQuota;
  enLecture: boolean;
}) {
  const valider = useValidateSeason();
  const devalider = useUnvalidateSeason();

  const { validated_count, has_volunteer_action, has_pending_volunteer_action, season_validated } = quota;
  // Seules les déclarations validées comptent (FR-008) ; une déclaration en
  // attente de modération se dit comme telle, pas « non déclaré » (#1044).
  const benevolat = has_volunteer_action
    ? "validé"
    : has_pending_volunteer_action
      ? "en attente de validation"
      : "non validé";

  async function handleValider() {
    try {
      await valider.mutateAsync({ athleteId, season });
      toast.success(`${seasonLabel(season)} validée.`);
    } catch {
      toast.error(ECHEC_VALIDATION);
    }
  }

  async function handleDevalider() {
    try {
      await devalider.mutateAsync({ athleteId, season });
      toast.success(`${seasonLabel(season)} dévalidée.`);
    } catch {
      toast.error(ECHEC_DEVALIDATION);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
      {/* FR-012 — indicatif, ne bloque jamais la validation (FR-011). */}
      <p style={{ fontSize: 12, color: "var(--tcn-text-faint)", opacity: enLecture ? 0.5 : 1 }}>
        {validated_count}/3 épreuves validées · bénévolat {benevolat}
      </p>
      {season_validated ? (
        <Button
          variant="secondary"
          onClick={handleDevalider}
          disabled={devalider.isPending || enLecture}
          aria-busy={devalider.isPending || enLecture}
        >
          Dévalider la saison
        </Button>
      ) : (
        <Button
          variant="secondary"
          onClick={handleValider}
          disabled={valider.isPending || enLecture}
          aria-busy={valider.isPending || enLecture}
        >
          Valider la saison
        </Button>
      )}
    </div>
  );
}

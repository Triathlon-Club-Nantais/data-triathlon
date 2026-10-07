"use client";
import Link from "next/link";
import { nomDe } from "@/components/admin/MergeAthletesDialog";
import { AthleteAdminPanel } from "@/components/athletes/AthleteAdminPanel";
import { AthleteDetachAction } from "@/components/athletes/AthleteDetachAction";
import { ParticipationAdminActions } from "@/components/athletes/ParticipationAdminActions";
import type { IdentityReviewCandidate, IdentityReviewConflict, IdentityReviewReason } from "@/lib/types";

export const IDENTITY_HELP_URL = "/admin/guide#identites";

const REASON_HELP: Record<IdentityReviewReason, string> = {
  same_course_bibs:
    "Deux dossards sur une même épreuve : ce sont deux personnes sous une même fiche. Séparez les résultats de l'autre vers une nouvelle fiche, rattachez-les à sa fiche existante, ou supprimez un doublon.",
  multi_club:
    "Un autre club que le sien apparaît sur cette fiche. Même personne qui a changé de club : confirmez ce club. Un homonyme : séparez ses résultats vers une nouvelle fiche.",
  club_homonym: "Deux fiches du même nom, dont une du club. Même personne : fusionnez. Deux personnes : écartez la paire.",
  swapped:
    "Nom et prénom inversés sur l'une des fiches. Même personne : inversez-les en corrigeant la fiche fautive, ou fusionnez. Une même épreuve courue par les deux fiches : ce sont deux personnes, écartez.",
  concatenated:
    "Le nom complet d'une fiche fait face à une fiche découpée. Même personne : redécoupez nom et prénom en corrigeant la fiche, ou fusionnez. Une même épreuve courue par les deux fiches : ce sont deux personnes, écartez.",
  alias_collision:
    "Une fusion avait rattaché cette graphie à une autre fiche, puis une fiche a été recréée dessus. Même personne : fusionnez. Variante posée par erreur : retirez-la de la fiche.",
};

/** Ce que signifie le motif et quel geste choisir, avec le renvoi au guide (#1241). */
export function ReasonHelp({ candidate }: { candidate: IdentityReviewCandidate }) {
  // `alias_collision` : la première fiche est celle qui porte la variante (`alias_collisions`).
  const [owner] = candidate.athletes;
  return (
    <p className="text-[var(--tcn-text-faint)] text-xs">
      {REASON_HELP[candidate.reason]}{" "}
      {candidate.reason === "alias_collision" && (
        <>
          <Link href={`/athletes/${owner.id}#variantes`} className="underline underline-offset-2">
            Voir les variantes de {nomDe(owner)}
          </Link>
          {" · "}
        </>
      )}
      <Link href={IDENTITY_HELP_URL} className="underline underline-offset-2">
        Aide
      </Link>
    </p>
  );
}

/**
 * Les gestes sur les fiches elles-mêmes, selon le motif. « Séparer » ne lit les
 * résultats de la fiche qu'à l'ouverture de sa fenêtre (`AthleteDetachAction`).
 */
export function RecordGestures({ candidate }: { candidate: IdentityReviewCandidate }) {
  if (candidate.reason === "swapped" || candidate.reason === "concatenated") {
    return (
      <div className="flex flex-wrap gap-2">
        {candidate.athletes.map((athlete) => (
          <AthleteAdminPanel key={athlete.id} athlete={athlete} withMerge={false} />
        ))}
      </div>
    );
  }
  if (candidate.reason === "multi_club") {
    const [athlete] = candidate.athletes;
    return <AthleteDetachAction athleteId={athlete.id} athleteName={nomDe(athlete)} openNewRecord={false} />;
  }
  return null;
}

/** Les actions d'une ligne de résultat en conflit : rattacher, supprimer, et séparer sur une fiche partagée. */
export function ResultGestures({
  candidate,
  conflict,
  entry,
}: {
  candidate: IdentityReviewCandidate;
  conflict: IdentityReviewConflict;
  entry: IdentityReviewConflict["entries"][number];
}) {
  const athlete = candidate.athletes.find((candidateAthlete) => candidateAthlete.id === entry.athlete_id);
  if (!athlete) return null;
  // Deux lignes d'une même épreuve : le dossard les distingue dans les libellés.
  const title = `${conflict.course_name}, ${entry.bib ? `dossard ${entry.bib}` : "sans dossard"}`;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <ParticipationAdminActions
        resultat={{
          id: entry.participation_id,
          epreuve: title,
          date: conflict.event_date,
          coureur: nomDe(athlete),
          coureurId: athlete.id,
        }}
      />
      {candidate.reason === "same_course_bibs" && (
        <AthleteDetachAction
          athleteId={athlete.id}
          athleteName={nomDe(athlete)}
          preselectedIds={[entry.participation_id]}
          label="Séparer"
          ariaLabel={`Séparer le résultat de « ${title} » vers une nouvelle fiche`}
          openNewRecord={false}
        />
      )}
    </div>
  );
}

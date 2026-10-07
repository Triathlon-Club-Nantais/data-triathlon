"use client";
import Link from "next/link";
import { nomDe } from "@/components/admin/MergeAthletesDialog";
import { AthleteAdminPanel } from "@/components/athletes/AthleteAdminPanel";
import { AthleteDetachAction } from "@/components/athletes/AthleteDetachAction";
import { ParticipationAdminActions } from "@/components/athletes/ParticipationAdminActions";
import { useAthleteResults } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import type {
  IdentityReviewAthlete,
  IdentityReviewCandidate,
  IdentityReviewConflict,
  IdentityReviewReason,
} from "@/lib/types";

export const AIDE_IDENTITES = "/admin/guide#identites";

const AIDE: Record<IdentityReviewReason, string> = {
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
export function AideDuMotif({ candidate }: { candidate: IdentityReviewCandidate }) {
  // `alias_collision` : la première fiche est celle qui porte la variante (`alias_collisions`).
  const [porteuse] = candidate.athletes;
  return (
    <p className="text-[var(--tcn-text-faint)] text-xs">
      {AIDE[candidate.reason]}{" "}
      {candidate.reason === "alias_collision" && (
        <>
          <Link href={`/athletes/${porteuse.id}#variantes`} className="underline underline-offset-2">
            Voir les variantes de {nomDe(porteuse)}
          </Link>
          {" · "}
        </>
      )}
      <Link href={AIDE_IDENTITES} className="underline underline-offset-2">
        Aide
      </Link>
    </p>
  );
}

/**
 * « Séparer » d'`AthleteDetachAction`, sur les résultats lus depuis la fiche
 * publique. Lus seulement pour qui détient les deux pouvoirs du geste.
 */
function Separer({
  fiche,
  preselection,
  texte,
  ariaLabel,
}: {
  fiche: IdentityReviewAthlete;
  preselection?: number[];
  texte?: string;
  ariaLabel?: string;
}) {
  const session = useHydratedSession();
  const pouvoirs = session.data?.permissions ?? [];
  const peutSeparer = pouvoirs.includes("athletes:write") && pouvoirs.includes("participations:reassign");
  const resultats = useAthleteResults(fiche.id, peutSeparer);
  if (!resultats.data) return null;
  return (
    <AthleteDetachAction
      athleteId={fiche.id}
      athleteName={nomDe(fiche)}
      participations={resultats.data}
      preselection={preselection}
      texte={texte}
      ariaLabel={ariaLabel}
      ouvrirLaNouvelleFiche={false}
    />
  );
}

/** Les gestes sur les fiches elles-mêmes, selon le motif. */
export function GestesDesFiches({ candidate }: { candidate: IdentityReviewCandidate }) {
  if (candidate.reason === "swapped" || candidate.reason === "concatenated") {
    return (
      <div className="flex flex-wrap gap-2">
        {candidate.athletes.map((fiche) => (
          <AthleteAdminPanel key={fiche.id} athlete={fiche} avecFusion={false} />
        ))}
      </div>
    );
  }
  if (candidate.reason === "multi_club") return <Separer fiche={candidate.athletes[0]} />;
  return null;
}

/** Les actions d'une ligne de résultat en conflit : rattacher, supprimer, et séparer sur une fiche partagée. */
export function GestesDuResultat({
  candidate,
  conflit,
  ligne,
}: {
  candidate: IdentityReviewCandidate;
  conflit: IdentityReviewConflict;
  ligne: IdentityReviewConflict["entries"][number];
}) {
  const fiche = candidate.athletes.find((athlete) => athlete.id === ligne.athlete_id);
  if (!fiche) return null;
  // Deux lignes d'une même épreuve : le dossard les distingue dans les libellés.
  const intitule = `${conflit.course_name}, ${ligne.bib ? `dossard ${ligne.bib}` : "sans dossard"}`;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <ParticipationAdminActions
        resultat={{
          id: ligne.participation_id,
          epreuve: intitule,
          date: conflit.event_date,
          coureur: nomDe(fiche),
          coureurId: fiche.id,
        }}
      />
      {candidate.reason === "same_course_bibs" && (
        <Separer
          fiche={fiche}
          preselection={[ligne.participation_id]}
          texte="Séparer"
          ariaLabel={`Séparer le résultat de « ${intitule} » vers une nouvelle fiche`}
        />
      )}
    </div>
  );
}

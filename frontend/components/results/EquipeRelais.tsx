import type { Participation } from "@/lib/types";
import { estRelais } from "@/lib/utils/relais";

// Une composition n'existe que sur un relais (le serveur le garantit, que le
// drapeau soit porté par le résultat ou par l'épreuve) : sa présence suffit.
function equipiers(participation: Participation) {
  return participation.teammates ?? [];
}

/** Nom de l'équipe d'un relais attribué (#894), ou `null` : le titre d'une ligne de classement. */
export function nomEquipe(participation: Participation): string | null {
  return equipiers(participation).length > 0 ? (participation.team_name ?? null) : null;
}

/**
 * Nomme les équipiers d'un relais attribué (#894).
 *
 * Rend le JSX et non la chaîne : la grille et la carte d'un même écran le
 * partagent, et c'est au rendu que les deux arbres ont déjà divergé (#461).
 * `avecEquipe` (fiche athlète, titrée par l'épreuve) préfixe « Relais » et le nom
 * de l'équipe, puis nomme les **autres** équipiers en « Prénom NOM », comme le
 * titre de la fiche et `PodiumsList` ; un relais sans composition y reste
 * signalé, puisqu'il sort des tuiles (FR-011). Sans `avecEquipe` (classement
 * de l'épreuve), la liste « NOM Prénom » du classement, rien sans composition.
 */
export function EquipeRelais({
  participation,
  avecEquipe = true,
  athleteId,
}: {
  participation: Participation;
  avecEquipe?: boolean;
  athleteId?: number;
}) {
  const liste = equipiers(participation);
  let texte: string | null;
  if (!avecEquipe) {
    texte = liste.length
      ? liste.map((a) => [a.nom, a.prenom].filter(Boolean).join(" ")).join(", ")
      : null;
  } else if (liste.length || estRelais(participation)) {
    const equipe = liste.length && participation.team_name ? ` · ${participation.team_name}` : "";
    const autres = liste
      .filter((a) => a.id !== athleteId)
      .map((a) => [a.prenom, a.nom].filter(Boolean).join(" "));
    texte = `Relais${equipe}${autres.length ? `, avec ${autres.join(", ")}` : ""}`;
  } else {
    texte = null;
  }
  if (texte === null) return null;
  return (
    <span style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--tcn-text-muted)" }}>
      {texte}
    </span>
  );
}

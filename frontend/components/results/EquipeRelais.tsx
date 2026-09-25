import type { Participation } from "@/lib/types";

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
 * `avecEquipe` préfixe le nom de l'équipe là où le titre de la ligne ne le porte
 * pas déjà (fiche athlète, titrée par l'épreuve). Rien pour un résultat dont la
 * composition n'est pas posée.
 */
export function EquipeRelais({
  participation,
  avecEquipe = true,
}: {
  participation: Participation;
  avecEquipe?: boolean;
}) {
  const liste = equipiers(participation);
  if (liste.length === 0) return null;
  const noms = liste.map((a) => [a.nom, a.prenom].filter(Boolean).join(" ")).join(", ");
  const equipe = participation.team_name ? ` · ${participation.team_name}` : "";
  return (
    <span style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--tcn-text-muted)" }}>
      {avecEquipe ? `Relais${equipe} : ${noms}` : noms}
    </span>
  );
}

import { describeQualityIssues } from "@/lib/quality";

/**
 * Marque « données douteuses » d'une épreuve (#486, RES-10).
 *
 * L'API publiait `is_reliable` et `quality_issues` depuis l'origine, `lib/quality.ts`
 * savait les mettre en phrases, et le profil athlète les affichait — mais ni la page
 * épreuve ni la liste ne les lisaient. Ce composant n'ajoute donc aucune donnée : il
 * lit ce qui existait déjà, là où on regarde les chiffres.
 *
 * Le vocabulaire vient de `describeQualityIssues`, partagé avec `EventsTable` du profil :
 * un même code d'anomalie ne doit pas se dire de deux façons selon l'écran.
 *
 * `role="img"` + `title` + `aria-label`, patron posé par #472 pour le marqueur de split
 * illisible : la marque **informe**, elle ne commande rien, et son texte existe pour un
 * lecteur d'écran comme au survol.
 */
export function ReliabilityMark({
  isReliable,
  issues,
  compact = false,
}: {
  isReliable?: boolean | null;
  issues?: Record<string, number> | null;
  /** En liste, un pictogramme seul : la colonne n'a pas la place d'un libellé. */
  compact?: boolean;
}) {
  // `null` n'est pas « douteuse » : c'est une épreuve jamais évaluée, état normal
  // des imports antérieurs au calcul de fiabilité. Seul `false` est un verdict.
  if (isReliable !== false) return null;

  const details = describeQualityIssues(issues);
  const motif = details.length
    ? `Fiabilité incertaine : ${details.join(" ; ")}.`
    : "Fiabilité des données incertaine chez le chronométreur — aucune anomalie détaillée.";

  return (
    <span
      role="img"
      title={motif}
      // En liste, le nom accessible se réduit au verdict : la forme compacte vit
      // **dans** le lien de ligne d'`EventList`, dont le nom accessible absorbe
      // son sous-arbre — le détail complet y ajoutait ~120 caractères par ligne,
      // relus à chaque parcours au rotor. Le détail reste au `title`, et la page
      // de l'épreuve l'énumère en toutes lettres.
      aria-label={compact ? "Données douteuses" : `Données douteuses. ${motif}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        minHeight: 24,
        padding: compact ? 0 : "3px 10px",
        borderRadius: 999,
        // Registre d'alerte, pas registre de donnée (#486, revue UI/UX). Le fond
        // `--tcn-fill` vaut exactement `--tcn-paper` : la marque se lisait à
        // 1,00:1 contre la page, en retrait des onze `MetaPill` voisines qui
        // portent `--tcn-surface`. Le seul élément qui dise « ne vous fiez pas à
        // ces chiffres » était le moins saillant de la rangée. Le triplet
        // `--tcn-warning-*` est celui de `PendingBadge`, même registre, même
        // écran public — aucun token inventé.
        border: compact ? "none" : "1px solid var(--tcn-warning-border)",
        background: compact ? "none" : "var(--tcn-warning-bg)",
        fontSize: 12,
        fontWeight: 700,
        color: compact ? "var(--tcn-text-body)" : "var(--tcn-warning-text)",
        cursor: "help",
      }}
    >
      <span aria-hidden style={{ color: compact ? "var(--tcn-text-faint)" : "inherit" }}>
        ⚠
      </span>
      {!compact && "Données douteuses"}
    </span>
  );
}

/**
 * Seuil au-delà duquel les inters publiés ne couvrent manifestement pas tout le
 * parcours. Mesuré : 5 épreuves sur 25 dans la base de dev
 * (`docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`, qui prime).
 */
export const SEUIL_ECART_EPREUVE = 0.01;

/**
 * Effectif minimal de lignes évaluables pour qu'une médiane soit une référence — même
 * garde que le marqueur de ligne (`ECART_MIN_LIGNES` de `RaceFinishers`). Sans elle, une
 * épreuve à une seule ligne évaluable ferait une affirmation sur tout le classement.
 */
export const ECART_MIN_LIGNES_EPREUVE = 10;

/**
 * Le second signal de `RES-10`, et le plus important du sondage : quand **toutes** les
 * lignes s'écartent du même ordre, ce n'est pas une ligne qui est fausse, c'est une
 * propriété de la mesure sur cette épreuve. On le dit **une fois**, ici — le répéter sur
 * chacune des 681 lignes de la course 47 serait du bruit.
 */
export function SplitCoverageNote({
  median,
  rows,
}: {
  median: number | null;
  /** `split_gap_rows` : le nombre de lignes sur lesquelles la médiane est calculée. */
  rows: number;
}) {
  if (median == null || rows < ECART_MIN_LIGNES_EPREUVE) return null;
  // **Seul l'écart positif se dit.** Le signe porte l'information : positif, le total
  // couvre plus que la somme des inters — du temps hors des points de mesure. Négatif,
  // la somme dépasse le total, ce qui n'a pas d'explication bénigne (des inters
  // cumulés plutôt que par segment, typiquement) : affirmer alors « il en manque N % »
  // dirait exactement l'inverse de la vérité. Ce cas se tait, faute de savoir le dire.
  if (median <= SEUIL_ECART_EPREUVE) return null;

  const part = Math.round(median * 100);

  return (
    <p
      style={{
        margin: "12px 0 0",
        fontSize: 13,
        color: "var(--tcn-text-muted)",
      }}
    >
      Sur cette épreuve, les temps intermédiaires ne couvrent pas l&apos;intégralité du
      parcours — il en manque environ {part} % du temps total. Les temps affichés sont ceux
      publiés par le chronométreur.
    </p>
  );
}

// Échelle catégorielle **unique** des disciplines (TCN Design System). Elle a
// vécu en double jusqu'à #480 avec des familles et des couleurs qui ne
// s'accordaient pas. Tout part désormais d'ici.
//
// Chaque couleur porte du texte : `SportBadge` la passe à `tintedStyle`, qui en
// tire un libellé posé sur son propre aplat, donc 4,5:1 (WCAG 1.4.3). Mesuré,
// cela **exclut** `--tcn-grey-300` (3,44:1), `--tcn-grey-400` (4,37:1) et
// `--tcn-orange-200` (3,71:1), les trois tons les plus pâles de la palette.
// La couleur n'est jamais le seul encodage : le nom du type s'écrit à côté.
//
// Retoucher un token casse cette garantie en silence : `lib/sport-colors.test.ts`
// est ce qui l'attrape.
type FamilyName = "Triathlon" | "Swim & Run" | "Duathlon" | "Aquathlon" | "Run & Bike" | "Autres";

const FAMILY_COLORS: Record<FamilyName, string> = {
  Triathlon: "var(--tcn-orange)",
  "Swim & Run": "var(--tcn-ink-2)",
  Duathlon: "var(--tcn-orange-300)",
  Aquathlon: "var(--tcn-orange-deeper)",
  "Run & Bike": "var(--tcn-ink)",
  Autres: "var(--tcn-text-muted)",
};

function familyName(type: string): FamilyName {
  if (type.startsWith("triathlon")) return "Triathlon";
  if (type.startsWith("swimrun")) return "Swim & Run";
  if (type.startsWith("duathlon")) return "Duathlon";
  if (type === "aquathlon" || type === "aquarun") return "Aquathlon";
  if (type === "bike-run") return "Run & Bike";
  return "Autres";
}

/**
 * Couleur d'un type d'épreuve : la couleur de sa famille, rien d'autre.
 *
 * Ici, **#480 arbitre** : l'ancienne fonction rendait `--bike` au cyclisme,
 * `--run` au trail et à la course, `--swim` à l'aquathlon. Désormais `trail-*`,
 * `cyclisme-*`, `course-a-pied-*`, `cross-triathlon`, `raid-multisport` et
 * `swim-bike` rendent tous la couleur d'« Autres ». Perte assumée : ses
 * consommateurs, la `BarList` de `/club > Par discipline` et `SportBadge`,
 * écrivent le nom du type à côté de la pastille. Une seconde échelle « par
 * sport » serait exactement le doublon que ce fichier vient de supprimer.
 */
export function eventTypeColor(type: string | null | undefined): string {
  return FAMILY_COLORS[familyName((type ?? "").toLowerCase())];
}

/**
 * Version « encre » d'une couleur de discipline : assez sombre pour porter du
 * texte sur l'aplat correspondant, assez colorée pour rester reconnaissable.
 *
 * **`in oklab`, pas `in oklch`** : vers une encre quasi neutre mais bleutée,
 * l'arc de teinte le plus court d'OKLCH fait passer l'orange de marque par le
 * prune (#E9530E → #863c6c). En OKLab, la teinte ne dévie pas (#469).
 */
export function inkColor(color: string): string {
  return `color-mix(in oklab, ${color}, var(--foreground) var(--ink-mix))`;
}

/**
 * Règle d'or : **aplat = couleur pleine, texte = `…-ink`**.
 * Fond teinté à 14 %, libellé mixé vers `--foreground` de `--ink-mix`.
 */
export function tintedStyle(color: string): React.CSSProperties {
  return {
    color: inkColor(color),
    background: `color-mix(in oklab, ${color} 14%, transparent)`,
  };
}

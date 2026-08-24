// Échelle catégorielle **unique** des disciplines (TCN Design System). Elle a
// vécu en double jusqu'à #480 — ici pour les badges, dans `lib/utils/format.ts`
// pour la barre empilée du tableau de bord — avec des familles et des couleurs
// qui ne s'accordaient pas. Tout part désormais d'ici.
//
// Le choix des tokens obéit à DEUX contraintes, dans cet ordre :
//
//   1. **Chaque couleur porte du texte.** `SportBadge` la passe à `tintedStyle`,
//      qui en tire un libellé posé sur son propre aplat : il lui faut 4,5:1
//      (WCAG 1.4.3). Mesuré, cela **exclut** `--tcn-grey-300` (3,44:1),
//      `--tcn-grey-400` (4,37:1) et `--tcn-orange-200` (3,71:1) — les trois tons
//      les plus pâles de la palette.
//   2. **Deux familles voisines se distinguent** dans la barre empilée, au
//      seuil de 1,6:1. Six familles toutes distinguables deux à deux est
//      *impossible* sans quitter la palette (au mieux 4 couleurs) ; on tient
//      donc les 5 paires **adjacentes** — minimum obtenu : 2,27:1 — et la
//      couleur cesse d'être le seul encodage (libellés, filet, légende).
//
// Réordonner FAMILY_ORDER ou retoucher un token casse la seconde contrainte en
// silence : `lib/sport-colors.test.ts` est ce qui l'attrape.
export const FAMILY_ORDER = [
  "Triathlon",
  "Swim & Run",
  "Duathlon",
  "Aquathlon",
  "Run & Bike",
  "Autres",
] as const;

export type FamilyName = (typeof FAMILY_ORDER)[number];

/** Famille de discipline : ce que la légende nomme, et la couleur qui la code. */
export interface Discipline {
  name: FamilyName;
  color: string;
}

const FAMILY_COLORS: Record<FamilyName, string> = {
  Triathlon: "var(--tcn-orange)",
  "Swim & Run": "var(--tcn-ink-2)",
  Duathlon: "var(--tcn-orange-300)",
  Aquathlon: "var(--tcn-orange-deeper)",
  "Run & Bike": "var(--tcn-ink)",
  Autres: "var(--tcn-text-muted)",
};

/**
 * Famille d'un `event_type`. Les prédicats sont ceux qui vivaient dans
 * `lib/utils/format.ts` — `cross-triathlon` tombe donc dans « Autres », faute de
 * commencer par « triathlon ». C'est l'état antérieur, pas un arbitrage de #480.
 */
export function disciplineFamily(eventType: string | null | undefined): Discipline {
  const type = (eventType ?? "").toLowerCase();
  const name = familyName(type);
  return { name, color: FAMILY_COLORS[name] };
}

function familyName(type: string): FamilyName {
  if (type.startsWith("triathlon")) return "Triathlon";
  if (type.startsWith("swimrun")) return "Swim & Run";
  if (type.startsWith("duathlon")) return "Duathlon";
  if (type === "aquathlon" || type === "aquarun") return "Aquathlon";
  if (type === "bike-run") return "Run & Bike";
  return "Autres";
}

/** Couleur d'un type d'épreuve — la couleur de sa famille, rien d'autre. */
export function eventTypeColor(type: string | null | undefined): string {
  return disciplineFamily(type).color;
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

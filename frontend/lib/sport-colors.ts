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
//      donc les 5 paires **adjacentes dans l'ordre complet** — minimum
//      obtenu : 2,27:1.
//
// Cette seconde garantie est **conditionnée à la présence des six familles**,
// et ce n'est pas le cas courant : `aggregateDisciplines` n'émet que les
// familles réellement présentes dans `by_type`, donc une famille absente rend
// adjacentes deux couleurs que rien ne sépare. Mesuré sur les paires que cela
// rapproche : Triathlon/Duathlon 1,45:1 dès qu'il manque « Swim & Run » (un
// club sans swimrun — le cas le plus fréquent), Aquathlon/Autres 1,11:1 dès
// qu'il manque « Run & Bike » (`bike-run` est un type rare), 1,42:1 entre
// Triathlon et Autres. C'est **pour cette raison** que la couleur n'est jamais
// le seul encodage : filet blanc entre segments, nom écrit dans le segment,
// légende chiffrée dessous (WCAG 1.4.1, gardés par `DisciplineBar.test.tsx`)
// — eux valent pour tout sous-ensemble et à toute largeur.
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

/** Famille de discipline : ce que la légende nomme, la couleur qui la code, et
 *  l'encre qui écrit son nom **sur** cette couleur (aplat plein, pas un fond
 *  teinté — voir `FAMILY_INK`). */
export interface Discipline {
  name: FamilyName;
  color: string;
  ink: string;
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
 * Encre du libellé posé **sur l'aplat plein** de la famille (le segment de
 * `DisciplineBar`, pas le fond teinté à 14 % de `tintedStyle`, qui a sa propre
 * règle). `--tcn-surface` (blanc) ne tient 4,5:1 que sur les quatre aplats
 * sombres ; sur les deux aplats clairs de la rampe orange (`--tcn-orange`,
 * `--tcn-orange-300`), le blanc tombe à 3,68:1 et 2,53:1 (#480) — `--tcn-ink`
 * y grimpe à 4,54:1 et 6,58:1, le maximum que la palette permette sans
 * l'élargir.
 */
const FAMILY_INK: Record<FamilyName, string> = {
  Triathlon: "var(--tcn-ink)",
  "Swim & Run": "var(--tcn-surface)",
  Duathlon: "var(--tcn-ink)",
  Aquathlon: "var(--tcn-surface)",
  "Run & Bike": "var(--tcn-surface)",
  Autres: "var(--tcn-surface)",
};

/**
 * Famille d'un `event_type`. Les prédicats sont ceux qui vivaient dans
 * `lib/utils/format.ts` — `cross-triathlon` tombe donc dans « Autres », faute de
 * commencer par « triathlon ». C'est l'état antérieur, pas un arbitrage de #480.
 */
export function disciplineFamily(eventType: string | null | undefined): Discipline {
  const type = (eventType ?? "").toLowerCase();
  const name = familyName(type);
  return { name, color: FAMILY_COLORS[name], ink: FAMILY_INK[name] };
}

function familyName(type: string): FamilyName {
  if (type.startsWith("triathlon")) return "Triathlon";
  if (type.startsWith("swimrun")) return "Swim & Run";
  if (type.startsWith("duathlon")) return "Duathlon";
  if (type === "aquathlon" || type === "aquarun") return "Aquathlon";
  if (type === "bike-run") return "Run & Bike";
  return "Autres";
}

/**
 * Couleur d'un type d'épreuve — la couleur de sa famille, rien d'autre.
 *
 * Ici, **#480 arbitre** (contrairement à `disciplineFamily` ci-dessus, qui ne
 * fait que recopier les prédicats de `format.ts`) : l'ancienne fonction rendait
 * `--bike` au cyclisme, `--run` au trail et à la course, `--swim` à
 * l'aquathlon. Désormais `trail-*`, `cyclisme-*`, `course-a-pied-*`,
 * `cross-triathlon`, `raid-multisport` et `swim-bike` rendent tous la couleur
 * d'« Autres », donc la même. Perte assumée : ses deux consommateurs — la
 * `BarList` de `/club > Par discipline` et `SportBadge` — écrivent le nom du
 * type à côté de la pastille, la couleur n'y porte jamais l'information seule.
 * Une seconde échelle « par sport » serait exactement le doublon que ce fichier
 * vient de supprimer.
 */
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

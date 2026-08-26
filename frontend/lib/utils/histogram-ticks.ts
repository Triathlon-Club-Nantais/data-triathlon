/**
 * Ticks temporels de l'axe X de l'histogramme des temps (`/courses/[id]`, #129).
 *
 * Deux problèmes distincts qu'on veut résoudre au même endroit :
 *
 * 1. **Choix du pas** — sur un sprint (~1 h), un pas de 15 min rend 4-5 ticks
 *    lisibles ; sur un ironman (~15 h), 15 min en donnerait 60 (soupe). On
 *    veut viser 4-8 ticks quelle que soit la fenêtre, en piochant dans un
 *    ensemble d'intervalles humains (5 min, 10, 15, 20, 30, 1 h, 2 h…). Pas
 *    de progression arithmétique auto : `1 h 07 min` n'est pas un pas
 *    exploitable pour un lecteur.
 * 2. **Alignement** — le 1er tick n'est pas au 1er bucket brut. Il tombe sur
 *    le premier **multiple du pas** ≥ `startSec`. Sinon on lit « 1:07 »,
 *    « 1:22 », « 1:37 » — chiffres justes, illisibles.
 *
 * L'utilitaire est **pur et déterministe** (rien de `Math.random` / `Date.now`)
 * pour rester testable et permettre le SSR de la page `/courses/[id]`.
 */

/** Bandes de durée → pas de tick "humain". Le mapping est explicite plutôt
 *  qu'algorithmique : sur les gabarits de courses réels, quelques pas ronds
 *  (15/30/60/120 min) donnent des libellés lisibles ; un « plus fin qui
 *  rentre » algorithmique dériverait vers du 10 ou 20 min qui n'a pas la
 *  même clarté visuelle. Les bandes sont ordonnées croissant — la première
 *  qui matche gagne. Cf. AC5 de #129 (sprint 15 min · M 30 min · L 1 h ·
 *  XL/ironman 2 h).
 */
const TICK_STEPS: readonly { maxRangeSec: number; stepSec: number }[] = [
  { maxRangeSec: 90 * 60, stepSec: 15 * 60 },   // sprint : ≤ 1 h 30 → 15 min
  { maxRangeSec: 180 * 60, stepSec: 30 * 60 },  // M : ≤ 3 h → 30 min
  { maxRangeSec: 6 * 3600, stepSec: 60 * 60 },  // L : ≤ 6 h → 1 h
  { maxRangeSec: 15 * 3600, stepSec: 120 * 60 }, // XL / ironman : ≤ 15 h → 2 h
];
/** Fallback pour les courses au-delà de la dernière bande (théorique — le
 *  finisher le plus lent d'un ultra fait rarement > 30 h). */
const FALLBACK_STEP = 4 * 60 * 60;

/** Choisit un pas rond en fonction de la durée totale de la fenêtre. Voir
 *  `TICK_STEPS` pour les seuils. */
export function pickTickStep(startSec: number, endSec: number): number {
  const range = Math.max(0, endSec - startSec);
  for (const { maxRangeSec, stepSec } of TICK_STEPS) {
    if (range <= maxRangeSec) return stepSec;
  }
  return FALLBACK_STEP;
}

/** Renvoie la liste des ticks (en secondes) alignés sur un multiple du pas,
 *  couvrant `[startSec, endSec]`. Le 1er tick est le plus petit multiple du
 *  pas **≥ startSec** — pas le 1er bucket brut, qui donnerait des libellés
 *  du genre « 1:07 » (cf. AC3 de #129).
 */
export function buildTicks(startSec: number, endSec: number): number[] {
  const step = pickTickStep(startSec, endSec);
  const firstTick = Math.ceil(startSec / step) * step;
  const ticks: number[] = [];
  for (let t = firstTick; t <= endSec; t += step) ticks.push(t);
  return ticks;
}

/** Format court pour un tick temporel : `H:MM` (pas de secondes, pas de padding
 *  d'heures). Ex. 3900s → « 1:05 », 5400s → « 1:30 », 30600s → « 8:30 ».
 *  Un tick à 0s reste « 0:00 » — cas rare mais valide.
 */
export function formatTickLabel(sec: number): string {
  const total = Math.max(0, Math.round(sec));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  return `${h}:${m.toString().padStart(2, "0")}`;
}

/**
 * Convertit un temps normalisé `"HH:MM:SS"` (`app/scrapers/utils.py` côté
 * backend) en secondes, pour placer un repère sur l'histogramme (US2, #466).
 * `null` sur toute forme non conforme plutôt qu'un `NaN` qui produirait un
 * repère hors champ silencieux.
 */
export function parseTotalTimeSeconds(totalTime: string | null | undefined): number | null {
  if (!totalTime) return null;
  const parts = totalTime.split(":");
  if (parts.length !== 3) return null;
  const [h, m, s] = parts.map(Number);
  if (![h, m, s].every(Number.isFinite)) return null;
  return h * 3600 + m * 60 + s;
}

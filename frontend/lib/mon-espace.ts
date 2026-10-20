import type { Participation } from "@/lib/types";
import { bestTimes, countsAsPerformance } from "@/lib/utils/best-times";
import { disciplineOf, formatToken } from "@/lib/utils/format";
import { estRelais } from "@/lib/utils/relais";
import { compteMaSaison } from "@/lib/utils/ma-saison";
import { rankRatio } from "@/lib/utils/ranking";
import { secondsFromHms } from "@/lib/utils/time";

export interface ChiffresSaison {
  epreuves: number;
  podiums: number;
  /** Somme des distances connues (hors relais). */
  km: number;
  /** Épreuves hors relais sans distance : `km` est alors un minimum. */
  sansDistance: number;
  tempsSecondes: number;
  /** Meilleur « top % » (le plus petit), null si aucune épreuve classable. */
  meilleurRatio: number | null;
}

/**
 * Les cinq chiffres de « Mes chiffres ». Résultats en attente exclus ; km, temps
 * et classement relatif ignorent les relais (distance et temps d'équipe).
 */
export function chiffresSaison(participations: Participation[]): ChiffresSaison {
  const validees = participations.filter((p) => !p.is_pending_validation);
  const { epreuves, podiums } = compteMaSaison(validees, "all");
  let km = 0;
  let sansDistance = 0;
  let tempsSecondes = 0;
  let meilleurRatio: number | null = null;
  for (const p of validees) {
    if (estRelais(p)) continue;
    if (p.course.distance_km == null) sansDistance += 1;
    else km += p.course.distance_km;
    tempsSecondes += secondsFromHms(p.total_time) ?? 0;
    const pourcent = rankRatio(p).ratio?.percent;
    if (pourcent !== undefined && (meilleurRatio === null || pourcent < meilleurRatio)) meilleurRatio = pourcent;
  }
  return { epreuves, podiums, km, sansDistance, tempsSecondes, meilleurRatio };
}

/** Saison précédente jusqu'à la même date un an plus tôt (bornes fixes au 1er septembre). */
export function fenetreSaisonPrecedente(season: number, today: Date): { start: string; end: string } {
  const start = `${season - 1}-09-01`;
  const anPlusTot = new Date(today);
  anPlusTot.setUTCFullYear(today.getUTCFullYear() - 1);
  const end = [anPlusTot.toISOString().slice(0, 10), `${season}-08-31`].sort()[0];
  return { start, end: end < start ? start : end };
}

/** Mes épreuves (hors relais et saisies en attente) comptées par (discipline, format), les plus courues d'abord. */
export function repartitionDisciplines(participations: Participation[]): [string, number][] {
  const compte = new Map<string, number>();
  for (const p of participations) {
    if (p.is_pending_validation || estRelais(p)) continue;
    const cle = `${disciplineOf(p.course.event_type)}|${formatToken(p.course.event_type, p.course.distance_km)}`;
    compte.set(cle, (compte.get(cle) ?? 0) + 1);
  }
  return [...compte].sort((a, b) => b[1] - a[1]);
}

export const SEGMENTS = [
  { cle: "swim", libelle: "Natation" },
  { cle: "bike", libelle: "Vélo" },
  { cle: "run", libelle: "Course à pied" },
] as const;

export type CleSegment = (typeof SEGMENTS)[number]["cle"];

/**
 * Ma médiane de natation, vélo et course par `event_type`. Seules comptent les lignes
 * dont les splits sont évaluables côté serveur (`split_gap_ratio`), qui valent
 * performance et dont l'épreuve a des splits fiables (`has_reliable_splits`, le
 * critère de la médiane du club).
 */
export function mesMediansDeSplits(participations: Participation[]): Map<string, Record<CleSegment, number>> {
  const valeurs = new Map<string, Record<CleSegment, number[]>>();
  for (const p of participations) {
    if (!countsAsPerformance(p) || !p.course.has_reliable_splits || p.split_gap_ratio == null) continue;
    const secondes = SEGMENTS.map(({ cle }) => secondsFromHms(p.splits?.[cle]));
    if (secondes.some((s) => !s)) continue;
    const type = p.course.event_type;
    const cible = valeurs.get(type) ?? { swim: [], bike: [], run: [] };
    SEGMENTS.forEach(({ cle }, i) => cible[cle].push(secondes[i]!));
    valeurs.set(type, cible);
  }
  const mediane = (v: number[]) => {
    const tri = [...v].sort((a, b) => a - b);
    const milieu = tri.length >> 1;
    return tri.length % 2 ? tri[milieu] : (tri[milieu - 1] + tri[milieu]) / 2;
  };
  return new Map([...valeurs].map(([type, v]) => [type, { swim: mediane(v.swim), bike: mediane(v.bike), run: mediane(v.run) }]));
}

/** `m:ss` sous l'heure, `h:mm:ss` au-delà. */
export function formatDuree(secondes: number): string {
  const s = Math.round(secondes);
  const ss = String(s % 60).padStart(2, "0");
  if (s < 3600) return `${Math.floor(s / 60)}:${ss}`;
  return `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${ss}`;
}

/** Écart de mon temps face au club en une phrase, « au même niveau » sous 30 s. */
export function ecartAuClub(moi: number, club: number): string {
  const delta = moi - club;
  if (Math.abs(delta) < 30) return "au même niveau";
  const minutes = Math.max(1, Math.round(Math.abs(delta) / 60));
  return `${minutes} min ${delta < 0 ? "plus rapide" : "plus lente"}`;
}

export function ecart(a: number, b: number): number {
  return a - b;
}

export function formatTempsTotal(secondes: number): string {
  const minutes = Math.floor((secondes % 3600) / 60);
  return `${Math.floor(secondes / 3600)} h ${String(minutes).padStart(2, "0")}`;
}

export interface Palier {
  type: "epreuves" | "podiums";
  reste: number;
  cible: number;
}

/** Le plus proche des deux paliers « égaler votre meilleure saison » (épreuves d'abord à égalité), null s'ils sont atteints. */
export function prochainPalier(
  courant: { epreuves: number; podiums: number },
  saisons: { epreuves: number; podiums: number }[],
): Palier | null {
  const paliers = (["epreuves", "podiums"] as const)
    .map((type) => {
      const cible = Math.max(0, ...saisons.map((s) => s[type]));
      return { type, reste: cible - courant[type], cible };
    })
    .filter((p) => p.reste > 0);
  return paliers.sort((a, b) => a.reste - b.reste)[0] ?? null;
}

export interface RecordPersonnel {
  format: string;
  discipline: string;
  meilleur: { temps: string; participation: Participation };
  record: { temps: string; participation: Participation };
  badge: "record" | "premiere" | null;
}

/**
 * Meilleur temps de la sélection face au record de la carrière, par (discipline,
 * format). « 1re fois » : un seul résultat de carrière sur ce format ; « record
 * perso » : la sélection porte le record et il en bat un autre.
 */
export function recordsPersonnels(selection: Participation[], carriere: Participation[]): RecordPersonnel[] {
  const records = new Map(bestTimes(carriere).map((b) => [`${b.discipline}|${b.format}`, b]));
  const effectifs = new Map<string, number>();
  for (const p of carriere) {
    const [b] = bestTimes([p]);
    if (b) effectifs.set(`${b.discipline}|${b.format}`, (effectifs.get(`${b.discipline}|${b.format}`) ?? 0) + 1);
  }
  return bestTimes(selection).map(({ discipline, format, participation }) => {
    const cle = `${discipline}|${format}`;
    const record = records.get(cle)?.participation ?? participation;
    let badge: RecordPersonnel["badge"] = null;
    if (effectifs.get(cle) === 1) badge = "premiere";
    else if (record.id === participation.id) badge = "record";
    return {
      format,
      discipline,
      meilleur: { temps: participation.total_time ?? "", participation },
      record: { temps: record.total_time ?? "", participation: record },
      badge,
    };
  });
}

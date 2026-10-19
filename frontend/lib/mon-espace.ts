import type { Participation } from "@/lib/types";
import { bestTimes } from "@/lib/utils/best-times";
import { estRelais } from "@/lib/utils/relais";
import { compteMaSaison } from "@/lib/utils/ma-saison";
import { rankRatio } from "@/lib/utils/ranking";
import { secondsFromHms } from "@/lib/utils/time";

export interface ChiffresSaison {
  epreuves: number;
  podiums: number;
  km: number;
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
  let tempsSecondes = 0;
  let meilleurRatio: number | null = null;
  for (const p of validees) {
    if (estRelais(p)) continue;
    km += p.course.distance_km ?? 0;
    tempsSecondes += secondsFromHms(p.total_time) ?? 0;
    const pourcent = rankRatio(p).ratio?.percent;
    if (pourcent !== undefined && (meilleurRatio === null || pourcent < meilleurRatio)) meilleurRatio = pourcent;
  }
  return { epreuves, podiums, km, tempsSecondes, meilleurRatio };
}

/** Saison précédente jusqu'à la même date un an plus tôt (bornes fixes au 1er septembre). */
export function fenetreSaisonPrecedente(season: number, today: Date): { start: string; end: string } {
  const start = `${season - 1}-09-01`;
  const anPlusTot = new Date(today);
  anPlusTot.setUTCFullYear(today.getUTCFullYear() - 1);
  const end = [anPlusTot.toISOString().slice(0, 10), `${season}-08-31`].sort()[0];
  return { start, end: end < start ? start : end };
}

export function ecart(a: number, b: number): number {
  return a - b;
}

export function formatTempsTotal(secondes: number): string {
  const minutes = Math.floor((secondes % 3600) / 60);
  return `${Math.floor(secondes / 3600)} h ${String(minutes).padStart(2, "0")}`;
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

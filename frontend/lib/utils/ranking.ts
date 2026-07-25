// Ratio place / nombre de classés d'une participation. Fonctions pures et testables.
import type { Participation } from "@/lib/types";

export interface RankRatio {
  rank: number;
  total: number;
  /** Percentile arrondi au supérieur : 42e sur 300 → 14 (« Top 14 % »). */
  percent: number;
}

// Sous deux classés, le ratio ne signale qu'un import partiel.
const MIN_CLASSES = 2;

/** Ratio d'une participation, ou `null` si les données ne le permettent pas. */
export function rankRatio(p: Participation): RankRatio | null {
  const rank = p.rank_overall;
  const total = p.course_finishers ?? null;
  if (rank == null || rank < 1) return null;
  if (total == null || total < MIN_CLASSES) return null;
  // Import partiel : plus de rangs que de classés en base. Un « Top 210 % »
  // serait pire que pas de ratio du tout.
  if (rank > total) return null;
  // Multiplication avant division réduit les erreurs de précision flottante.
  return { rank, total, percent: Math.ceil((rank * 100) / total) };
}

export interface RatioEntry {
  participation: Participation;
  ratio: RankRatio;
}

/** Meilleure performance rapportée au champ de la course (ratio brut, non arrondi). */
export function bestRatio(parts: Participation[]): RatioEntry | null {
  let best: RatioEntry | null = null;
  for (const participation of parts) {
    const ratio = rankRatio(participation);
    if (!ratio) continue;
    if (!best) {
      best = { participation, ratio };
      continue;
    }
    const candidate = ratio.rank / ratio.total;
    const incumbent = best.ratio.rank / best.ratio.total;
    if (candidate < incumbent || (candidate === incumbent && ratio.rank < best.ratio.rank)) {
      best = { participation, ratio };
    }
  }
  return best;
}

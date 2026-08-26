// Ratio place / nombre de classés d'une participation. Fonctions pures et testables.
import type { Participation } from "@/lib/types";

interface RankRatio {
  rank: number;
  total: number;
  /** Percentile arrondi au supérieur : 42e sur 300 → 14 (« Top 14 % »). */
  percent: number;
}

/**
 * Le refus d'un ratio a deux natures qu'on distingue à l'affichage :
 * `unreliable` = la course est marquée `is_reliable=false` (données douteuses
 * chez le chronométreur : dossards en doublon, trous dans le classement…) →
 * signal explicite à l'utilisateur. `incomplete` = rang absent ou compte de
 * classés absent/incohérent → cellule vide, cas neutre.
 */
type RankRatioReason = "unreliable" | "incomplete";

interface RankRatioResult {
  ratio: RankRatio | null;
  reason?: RankRatioReason;
}

// Sous deux classés, le ratio ne signale qu'un import partiel.
const MIN_CLASSES = 2;

/** Ratio d'une participation, avec la raison motivant un `null`. */
export function rankRatio(p: Participation): RankRatioResult {
  // Course explicitement marquée non fiable : mieux vaut ne rien afficher
  // qu'un ratio faux. `=== false` seulement : absent/null continue de produire un ratio.
  if (p.course.is_reliable === false) return { ratio: null, reason: "unreliable" };
  const rank = p.rank_overall;
  const total = p.course_finishers ?? null;
  if (rank == null || rank < 1) return { ratio: null, reason: "incomplete" };
  if (total == null || total < MIN_CLASSES) return { ratio: null, reason: "incomplete" };
  // Import partiel : plus de rangs que de classés en base. Un « Top 210 % »
  // serait pire que pas de ratio du tout.
  if (rank > total) return { ratio: null, reason: "incomplete" };
  // Multiplication avant division réduit les erreurs de précision flottante.
  return { ratio: { rank, total, percent: Math.ceil((rank * 100) / total) } };
}

interface RatioEntry {
  participation: Participation;
  ratio: RankRatio;
}

/** Meilleure performance rapportée au champ de la course (ratio brut, non arrondi). */
export function bestRatio(parts: Participation[]): RatioEntry | null {
  let best: RatioEntry | null = null;
  for (const participation of parts) {
    const { ratio } = rankRatio(participation);
    if (!ratio) continue;
    if (!best) {
      best = { participation, ratio };
      continue;
    }
    // Produits croisés plutôt que deux divisions : les totaux sont > 0, donc
    // l'ordre est préservé, et la comparaison reste exacte (entiers).
    const candidate = ratio.rank * best.ratio.total;
    const incumbent = best.ratio.rank * ratio.total;
    if (candidate < incumbent || (candidate === incumbent && ratio.rank < best.ratio.rank)) {
      best = { participation, ratio };
    }
  }
  return best;
}

export interface ProgressionPoint {
  participationId: number;
  eventDate: string;
  percent: number;
}

/**
 * Série chronologique du ratio de performance, la plus ancienne épreuve en
 * premier. Exclut les participations sans ratio exploitable et celles sans
 * date d'épreuve — un point sans date ne peut pas se ranger dans l'ordre
 * chronologique.
 */
export function progressionSeries(parts: Participation[]): ProgressionPoint[] {
  return parts
    .map((p) => ({ participation: p, ratio: rankRatio(p).ratio }))
    .filter(
      (entry): entry is { participation: Participation; ratio: RankRatio } =>
        entry.ratio != null && entry.participation.course.event_date != null,
    )
    .sort((a, b) => a.participation.course.event_date!.localeCompare(b.participation.course.event_date!))
    .map((entry) => ({
      participationId: entry.participation.id,
      eventDate: entry.participation.course.event_date!,
      percent: entry.ratio.percent,
    }));
}

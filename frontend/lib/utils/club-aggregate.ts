import type { Participation, DisciplinePodiumCounts } from "@/lib/types";
import type { RankType } from "@/lib/rank";
import { disciplineOf } from "@/lib/utils/format";

const RANK_KEYS: Record<RankType, (keyof Participation)[]> = {
  scratch: ["rank_overall"],
  category: ["rank_category"],
  gender: ["rank_gender"],
  all: ["rank_overall", "rank_gender", "rank_category"],
};

/**
 * true si la participation a décroché un podium (top-3 sur le rang du mode).
 *
 * Miroir de `stats_service._rank_counters` côté backend — seul appelant : la
 * bande « Ma saison » (#502), qui compare des participations d'athlète que le
 * backend n'agrège pas.
 */
export function isPodium(p: Participation, rankType: RankType = "all"): boolean {
  return RANK_KEYS[rankType].some((key) => {
    const rank = p[key] as number | null | undefined;
    return rank != null && rank >= 1 && rank <= 3;
  });
}

/** Participations les plus récentes (par date d'épreuve puis ajout). */
export function recentParticipations(
  parts: Participation[],
  limit = 8,
): Participation[] {
  return [...parts]
    .sort((a, b) => {
      const da = a.course.event_date ?? "";
      const db = b.course.event_date ?? "";
      if (da !== db) return db.localeCompare(da);
      return (b.created_at ?? "").localeCompare(a.created_at ?? "");
    })
    .slice(0, limit);
}

export interface DisciplinePerformanceEntry {
  discipline: string;
  count: number;
  podiums: number;
}

const MODE_FIELD: Record<RankType, keyof DisciplinePodiumCounts> = {
  scratch: "overall",
  category: "category",
  gender: "gender",
  all: "all",
};

/**
 * Performance du club par discipline **normalisée** (podiums, croisés avec
 * `count` pour distinguer un vrai taux d'une petite série) — distinct du
 * décompte d'épreuves par discipline déjà rendu par `BarList`, qui ne dit que
 * le volume (US10, #466). `podiumsByType`/`countByType` arrivent déjà agrégés
 * côté serveur, par `event_type` **brut** (#642, `ClubSummary.podiums_by_
 * discipline`/`stats.by_type`) : plusieurs sous-types d'une même famille
 * (`triathlon-m`/`-s`/`-l`…) se fondent donc ici en une seule ligne, sur un
 * dictionnaire à quelques entrées — pas un tableau de participations. Une clé
 * dont la discipline ne se résout pas (`disciplineOf` vide) n'entre dans
 * aucun groupe. Triée par podiums décroissants puis par volume décroissant.
 */
export function disciplinePerformance(
  podiumsByType: Record<string, DisciplinePodiumCounts>,
  countByType: Record<string, number>,
  rankType: RankType = "all",
): DisciplinePerformanceEntry[] {
  const champ = MODE_FIELD[rankType];
  const map = new Map<string, DisciplinePerformanceEntry>();
  const types = new Set([...Object.keys(podiumsByType), ...Object.keys(countByType)]);
  for (const type of types) {
    const discipline = disciplineOf(type);
    if (!discipline) continue;
    let e = map.get(discipline);
    if (!e) {
      e = { discipline, count: 0, podiums: 0 };
      map.set(discipline, e);
    }
    e.count += countByType[type] ?? 0;
    e.podiums += podiumsByType[type]?.[champ] ?? 0;
  }
  return [...map.values()].sort(
    (a, b) => b.podiums - a.podiums || b.count - a.count,
  );
}

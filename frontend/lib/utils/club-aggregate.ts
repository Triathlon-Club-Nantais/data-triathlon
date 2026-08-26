import type { Participation } from "@/lib/types";
import type { RankType } from "@/lib/rank";

const RANK_KEYS: Record<RankType, (keyof Participation)[]> = {
  scratch: ["rank_overall"],
  category: ["rank_category"],
  gender: ["rank_gender"],
  all: ["rank_overall", "rank_gender", "rank_category"],
};

/**
 * true si la participation a décroché un podium (top-3 sur le rang du mode).
 *
 * Miroir de `stats_service._rank_counters` côté backend, et seul reste de
 * l'agrégation client de `/club` — celle-ci se calcule désormais en SQL
 * (#581). Unique appelant : la bande « Ma saison » (#502), qui compare des
 * participations d'athlète que le backend n'agrège pas.
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

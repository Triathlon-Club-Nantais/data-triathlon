// Agrégations club calculées côté client à partir des participations
// (filtrées sur le club). Fonctions pures et testables.
import type { Participation } from "@/lib/types";

export type PodiumScope = "overall" | "category" | "gender";

export interface BestRank {
  rank: number;
  scope: PodiumScope;
}

/** Meilleur classement d'une participation, tous scopes confondus (général > genre > catégorie à rang égal). */
export function bestRank(p: Participation): BestRank | null {
  const candidates: [number | null, PodiumScope][] = [
    [p.rank_overall, "overall"],
    [p.rank_gender, "gender"],
    [p.rank_category, "category"],
  ];
  let best: BestRank | null = null;
  for (const [rank, scope] of candidates) {
    if (rank != null && rank >= 1) {
      if (!best || rank < best.rank) best = { rank, scope };
    }
  }
  return best;
}

/** true si la participation est dans le top N sur l'un des trois classements. */
export function isTopN(p: Participation, n: number): boolean {
  const best = bestRank(p);
  return best !== null && best.rank <= n;
}

/** Meilleur classement top-3 d'une participation (général > genre > catégorie). */
export function bestPodiumRank(p: Participation): BestRank | null {
  const best = bestRank(p);
  return best && best.rank <= 3 ? best : null;
}

/** true si la participation a décroché un podium (top-3 sur l'un des classements). */
export function isPodium(p: Participation): boolean {
  return bestPodiumRank(p) !== null;
}

export interface RankCounters {
  victories: number;
  podiums: number;
  top10: number;
}

/**
 * Compteurs du dashboard, tous mesurés sur le même périmètre (général, genre ou
 * catégorie) pour rester emboîtés : victoires ≤ podiums ≤ top 10 (issue #77).
 */
export function rankCounters(parts: Participation[]): RankCounters {
  const counters: RankCounters = { victories: 0, podiums: 0, top10: 0 };
  for (const p of parts) {
    const best = bestRank(p);
    if (!best) continue;
    if (best.rank <= 1) counters.victories += 1;
    if (best.rank <= 3) counters.podiums += 1;
    if (best.rank <= 10) counters.top10 += 1;
  }
  return counters;
}

export interface PodiumEntry {
  participation: Participation;
  best: BestRank;
}

/** Liste des performances de podium, triées (rang asc puis date desc). */
export function listPodiums(parts: Participation[]): PodiumEntry[] {
  return parts
    .map((p) => ({ participation: p, best: bestPodiumRank(p) }))
    .filter((e): e is PodiumEntry => e.best !== null)
    .sort((a, b) => {
      if (a.best.rank !== b.best.rank) return a.best.rank - b.best.rank;
      const da = a.participation.course?.event_date ?? "";
      const db = b.participation.course?.event_date ?? "";
      return db.localeCompare(da);
    });
}

export interface RosterEntry {
  athleteId: number;
  name: string;
  gender: string;
  club: string | null;
  count: number;
  podiums: number;
  lastDate: string | null;
  lastEvent: string | null;
}

function fullName(p: Participation): string {
  const a = p.athlete;
  return [a?.prenom, a?.nom].filter(Boolean).join(" ") || "Athlète inconnu";
}

/** Roster du club : un athlète par ligne, trié par nb de courses puis podiums. */
export function buildRoster(parts: Participation[]): RosterEntry[] {
  const map = new Map<number, RosterEntry>();
  for (const p of parts) {
    const id = p.athlete?.id;
    if (id == null) continue;
    let e = map.get(id);
    if (!e) {
      e = {
        athleteId: id,
        name: fullName(p),
        gender: p.athlete?.gender ?? "",
        club: p.club ?? p.athlete?.club ?? null,
        count: 0,
        podiums: 0,
        lastDate: null,
        lastEvent: null,
      };
      map.set(id, e);
    }
    e.count += 1;
    if (isPodium(p)) e.podiums += 1;
    const date = p.course?.event_date ?? null;
    if (date && (!e.lastDate || date > e.lastDate)) {
      e.lastDate = date;
      e.lastEvent = p.course?.name ?? null;
    }
  }
  return [...map.values()].sort(
    (a, b) =>
      b.count - a.count || b.podiums - a.podiums || a.name.localeCompare(b.name),
  );
}

/** Participations les plus récentes (par date d'épreuve puis ajout). */
export function recentParticipations(
  parts: Participation[],
  limit = 8,
): Participation[] {
  return [...parts]
    .sort((a, b) => {
      const da = a.course?.event_date ?? "";
      const db = b.course?.event_date ?? "";
      if (da !== db) return db.localeCompare(da);
      return (b.created_at ?? "").localeCompare(a.created_at ?? "");
    })
    .slice(0, limit);
}

export interface ClubSummary {
  results: number;
  athletes: number;
  events: number;
  podiums: number;
}

/** Indicateurs de synthèse du club. */
export function clubSummary(parts: Participation[]): ClubSummary {
  const athletes = new Set<number>();
  const events = new Set<string>();
  let podiums = 0;
  for (const p of parts) {
    if (p.athlete?.id != null) athletes.add(p.athlete.id);
    const key = `${p.course?.name ?? ""}||${p.course?.event_date ?? ""}`;
    if (p.course?.name) events.add(key);
    if (isPodium(p)) podiums += 1;
  }
  return {
    results: parts.length,
    athletes: athletes.size,
    events: events.size,
    podiums,
  };
}

// Agrégations club calculées côté client à partir des participations
// (filtrées sur le club). Fonctions pures et testables.
import type { Participation } from "@/lib/types";
import type { RankType } from "@/lib/rank";

export type PodiumScope = "overall" | "category" | "gender";

interface BestRank {
  rank: number;
  scope: PodiumScope;
}

const ALL_CANDIDATES: readonly [PodiumScope, keyof Participation][] = [
  ["overall", "rank_overall"],
  ["gender", "rank_gender"],
  ["category", "rank_category"],
];

function candidatesFor(rankType: RankType | undefined): readonly [PodiumScope, keyof Participation][] {
  switch (rankType) {
    case "scratch": return [["overall", "rank_overall"]];
    case "category": return [["category", "rank_category"]];
    case "gender": return [["gender", "rank_gender"]];
    default: return ALL_CANDIDATES;
  }
}

/**
 * Meilleur classement d'une participation.
 *
 * En mode `"scratch"` / `"category"` / `"gender"`, ne regarde qu'un seul rang.
 * En mode `"all"` (défaut sans paramètre), prend le min des trois — ordre de
 * départage à rang égal : général > genre > catégorie.
 */
export function bestRank(p: Participation, rankType?: RankType): BestRank | null {
  let best: BestRank | null = null;
  for (const [scope, key] of candidatesFor(rankType)) {
    const rank = p[key] as number | null | undefined;
    if (rank != null && rank >= 1) {
      if (!best || rank < best.rank) best = { rank, scope };
    }
  }
  return best;
}

/** true si la participation est dans le top N sur le rang du mode courant. */
export function isTopN(p: Participation, n: number, rankType?: RankType): boolean {
  const best = bestRank(p, rankType);
  return best !== null && best.rank <= n;
}

/** Meilleur classement top-3 sur le rang du mode courant. */
export function bestPodiumRank(p: Participation, rankType?: RankType): BestRank | null {
  const best = bestRank(p, rankType);
  return best && best.rank <= 3 ? best : null;
}

/** true si la participation a décroché un podium (top-3 sur le rang du mode). */
export function isPodium(p: Participation, rankType?: RankType): boolean {
  return bestPodiumRank(p, rankType) !== null;
}

interface RankCounters {
  victories: number;
  podiums: number;
  top10: number;
}

/** Compteurs scalaires : modes scratch / category / all. */
interface RankCountersScalar extends RankCounters {
  kind: "scalar";
}

/** Compteurs dédoublés F/H : mode gender uniquement. */
interface RankCountersGender {
  kind: "gender";
  women: RankCounters;
  men: RankCounters;
}

/** Type discriminé retourné par `rankCounters` selon le mode. */
type RankCountersResult = RankCountersScalar | RankCountersGender;

/**
 * Compteurs du dashboard, tous mesurés sur le même périmètre pour rester
 * emboîtés : victoires ≤ podiums ≤ top 10 (issue #77).
 *
 * `rankType` :
 * - `"scratch"` / `"category"` : compte sur le seul rang correspondant.
 * - `"all"` ou `undefined` : min-des-trois (comportement historique).
 * - `"gender"` : ventile F/H via `athlete.gender` ; renvoie `{kind: "gender", women, men}`.
 *   Les athlètes sans genre renseigné ne sont comptés dans aucun des deux.
 */
export function rankCounters(parts: Participation[], rankType?: RankType): RankCountersResult {
  if (rankType === "gender") {
    const women: RankCounters = { victories: 0, podiums: 0, top10: 0 };
    const men: RankCounters = { victories: 0, podiums: 0, top10: 0 };
    for (const p of parts) {
      const g = (p.athlete?.gender ?? "").toUpperCase();
      if (g !== "F" && g !== "M") continue;
      const rank = p.rank_gender;
      if (rank == null || rank < 1) continue;
      const bucket = g === "F" ? women : men;
      if (rank <= 1) bucket.victories += 1;
      if (rank <= 3) bucket.podiums += 1;
      if (rank <= 10) bucket.top10 += 1;
    }
    return { kind: "gender", women, men };
  }
  const counters: RankCounters = { victories: 0, podiums: 0, top10: 0 };
  for (const p of parts) {
    const best = bestRank(p, rankType);
    if (!best) continue;
    if (best.rank <= 1) counters.victories += 1;
    if (best.rank <= 3) counters.podiums += 1;
    if (best.rank <= 10) counters.top10 += 1;
  }
  return { kind: "scalar", ...counters };
}

interface PodiumEntry {
  participation: Participation;
  best: BestRank;
}

/** Liste des performances de podium selon le mode, triées (rang asc puis date desc). */
export function listPodiums(parts: Participation[], rankType?: RankType): PodiumEntry[] {
  return parts
    .map((p) => ({ participation: p, best: bestPodiumRank(p, rankType) }))
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
  /**
   * Décompte de podiums ventilé par scope, **compteurs indépendants** : une
   * même participation qui est podium sur plusieurs dimensions (2e scratch +
   * 1er catégorie + 2e genre, cf. Hadrien à Mesquer) incrémente les trois
   * compteurs. La somme des trois est donc ≥ `podiums`, jamais égale.
   */
  podiumsByScope: Record<PodiumScope, number>;
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
        podiumsByScope: { overall: 0, gender: 0, category: 0 },
        lastDate: null,
        lastEvent: null,
      };
      map.set(id, e);
    }
    e.count += 1;
    let hasPodium = false;
    for (const [scope, key] of ALL_CANDIDATES) {
      const rank = p[key] as number | null | undefined;
      if (rank != null && rank >= 1 && rank <= 3) {
        e.podiumsByScope[scope] += 1;
        hasPodium = true;
      }
    }
    if (hasPodium) e.podiums += 1;
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

interface ClubSummary {
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

import type { Participation } from "@/lib/types";

const NON_FINISHER = new Set(["DNF", "DNS", "DSQ"]);

/** Vrai si le statut est un non-finisher porteur de sigle (DNF/DNS/DSQ). */
export function isNonFinisher(status: string | null | undefined): boolean {
  return NON_FINISHER.has((status ?? "").toUpperCase());
}

/**
 * Vrai si le statut est un finisher explicite (le backend pose « finisher »).
 * Un statut vide ou non reconnu n'est pas un finisher : il tombe dans les
 * « indéterminés » (cf. `countOutcomes`) pour ne pas gonfler le décompte.
 */
export function isFinisher(status: string | null | undefined): boolean {
  return (status ?? "").toLowerCase() === "finisher";
}

/** Décompte d'une liste ventilé en finishers / non-finishers / indéterminés. */
export interface OutcomeCounts {
  total: number;
  finishers: number;
  nonFinishers: number;
  unknown: number;
}

/**
 * Ventile les participations en trois catégories distinctes : finishers
 * (statut « finisher »), non-finishers (DNF/DNS/DSQ) et indéterminés (statut
 * vide ou inconnu). Les trois compteurs somment toujours à `total`.
 */
export function countOutcomes(parts: Participation[]): OutcomeCounts {
  let finishers = 0;
  let nonFinishers = 0;
  let unknown = 0;
  for (const p of parts) {
    if (isNonFinisher(p.status)) nonFinishers += 1;
    else if (isFinisher(p.status)) finishers += 1;
    else unknown += 1;
  }
  return { total: parts.length, finishers, nonFinishers, unknown };
}

// Rang de groupe : finishers d'abord, puis DNF, DSQ, DNS.
function groupRank(p: Participation): number {
  const s = (p.status ?? "").toUpperCase();
  if (s === "DNF") return 1;
  if (s === "DSQ") return 2;
  if (s === "DNS") return 3;
  return 0; // finisher, vide ou inconnu
}

// Secondes d'un temps "HH:MM:SS". Vide, invalide ou "00:00:00" = aucune valeur.
function timeSeconds(t: string | null): number {
  if (!t || t === "00:00:00") return Number.POSITIVE_INFINITY;
  const parts = t.split(":").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return Number.POSITIVE_INFINITY;
  return parts[0] * 3600 + parts[1] * 60 + parts[2];
}

function fullName(p: Participation): string {
  return `${p.athlete?.nom ?? ""} ${p.athlete?.prenom ?? ""}`.trim().toLowerCase();
}

/**
 * Trie les participations pour l'affichage : finishers d'abord (par rang
 * croissant, les non classés après), puis non-finishers groupés DNF → DSQ → DNS.
 * Au sein d'un groupe : par temps croissant (sans temps en fin), puis par nom.
 */
export function orderParticipations(parts: Participation[]): Participation[] {
  return [...parts].sort((a, b) => {
    const ga = groupRank(a);
    const gb = groupRank(b);
    if (ga !== gb) return ga - gb;

    if (ga === 0) {
      const ra = a.rank_overall ?? Number.POSITIVE_INFINITY;
      const rb = b.rank_overall ?? Number.POSITIVE_INFINITY;
      if (ra !== rb) return ra - rb;
      return fullName(a).localeCompare(fullName(b));
    }

    const ta = timeSeconds(a.total_time);
    const tb = timeSeconds(b.total_time);
    if (ta !== tb) return ta - tb;
    return fullName(a).localeCompare(fullName(b));
  });
}

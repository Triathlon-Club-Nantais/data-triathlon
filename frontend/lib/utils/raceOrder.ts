import type { Participation } from "@/lib/types";

const NON_FINISHER = new Set(["DNF", "DNS", "DSQ"]);

/** Vrai si le statut est un non-finisher porteur de sigle (DNF/DNS/DSQ). */
export function isNonFinisher(status: string | null | undefined): boolean {
  return NON_FINISHER.has((status ?? "").toUpperCase());
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

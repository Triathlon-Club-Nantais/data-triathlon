// Jeton court de format pour les FormatChip (XS / S / M / L, ou distance).
const SIZE_RE = /-(xs|s|m|l|xl)$/i;

export function formatToken(
  eventType: string | null | undefined,
  distanceKm?: number | null,
): string {
  const t = (eventType ?? "").toLowerCase();
  const m = t.match(SIZE_RE);
  if (m) return m[1].toUpperCase();
  if (distanceKm) {
    const n = Number.isInteger(distanceKm) ? distanceKm : Math.round(distanceKm);
    return `${n}km`;
  }
  // Repli : abréviation 2–3 lettres.
  if (t.startsWith("aquathlon")) return "AQ";
  if (t === "bike-run") return "B&R";
  if (t.startsWith("trail")) return "TR";
  if (t.startsWith("course-a-pied")) return "CAP";
  if (t.startsWith("cyclisme")) return "CYC";
  return "—";
}

// Famille de discipline (libellé + couleur du ramp TCN) pour les répartitions.
export interface Discipline {
  name: string;
  color: string;
}

export function disciplineFamily(eventType: string | null | undefined): Discipline {
  const t = (eventType ?? "").toLowerCase();
  if (t.startsWith("triathlon")) return { name: "Triathlon", color: "var(--tcn-orange)" };
  if (t.startsWith("swimrun")) return { name: "Swim & Run", color: "var(--tcn-ink)" };
  if (t.startsWith("duathlon")) return { name: "Duathlon", color: "var(--tcn-orange-300)" };
  if (t === "aquathlon" || t === "aquarun") return { name: "Aquathlon", color: "var(--tcn-grey-400)" };
  if (t === "bike-run") return { name: "Run & Bike", color: "var(--tcn-orange-200)" };
  return { name: "Autres", color: "var(--tcn-grey-300)" };
}

const FAMILY_ORDER = ["Triathlon", "Swim & Run", "Duathlon", "Aquathlon", "Run & Bike", "Autres"];

/** Agrège `by_type` (clés event_type → compte) en familles ordonnées avec %. */
export function aggregateDisciplines(
  byType: Record<string, number>,
): { name: string; color: string; count: number; pct: number }[] {
  const acc = new Map<string, { color: string; count: number }>();
  let total = 0;
  for (const [type, count] of Object.entries(byType)) {
    const fam = disciplineFamily(type);
    total += count;
    const e = acc.get(fam.name);
    if (e) e.count += count;
    else acc.set(fam.name, { color: fam.color, count });
  }
  return [...acc.entries()]
    .map(([name, { color, count }]) => ({ name, color, count, pct: total ? (count / total) * 100 : 0 }))
    .sort((a, b) => FAMILY_ORDER.indexOf(a.name) - FAMILY_ORDER.indexOf(b.name));
}

/** Formate la valeur numérique d'un pourcentage à la française (« 71,2 »),
 *  sans le symbole « % » (les appelants l'ajoutent eux-mêmes). */
export function pctFr(pct: number, decimals = 1): string {
  return pct.toFixed(decimals).replace(".", ",");
}

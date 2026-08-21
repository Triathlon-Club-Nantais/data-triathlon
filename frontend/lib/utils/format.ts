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

/**
 * Disciplines connues, telles qu'elles sont nommées dans `EVENT_TYPE_LABELS`.
 * Un `event_type` en base y ajoute son format (`triathlon-m`, `cyclisme-clm`,
 * `course-a-pied-semi`) : c'est ce préfixe qui nomme la discipline.
 */
const DISCIPLINES = [
  "triathlon",
  "duathlon",
  "swimrun",
  "aquathlon",
  "aquarun",
  "bike-run",
  "swim-bike",
  "cross-triathlon",
  "raid-multisport",
  "course-a-pied",
  "trail",
  "cyclisme",
];

/**
 * Discipline d'une épreuve, format mis de côté : « triathlon-m » → « triathlon ».
 *
 * Sert à filtrer par discipline sans éclater une même pratique en cinq entrées
 * de format (#489) — la taille reste lisible dans la colonne Format. Le plus
 * long préfixe l'emporte, pour que « cross-triathlon » et « cyclisme-route »
 * tombent sur la bonne discipline et non sur une homonymie de préfixe. Un type
 * inconnu est rendu tel quel : il vaut alors sa propre discipline, plutôt que
 * de disparaître dans un fourre-tout.
 */
export function disciplineOf(eventType: string | null | undefined): string {
  const type = (eventType ?? "").toLowerCase();
  if (!type) return "";
  let best = "";
  for (const discipline of DISCIPLINES) {
    if (type === discipline || type.startsWith(`${discipline}-`)) {
      if (discipline.length > best.length) best = discipline;
    }
  }
  return best || type;
}

// Famille de discipline (libellé + couleur du ramp TCN) pour les répartitions.
export interface Discipline {
  name: string;
  color: string;
}

function disciplineFamily(eventType: string | null | undefined): Discipline {
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

/** Ordinal français d'un classement : 1 → « 1er », 42 → « 42e ». */
export function ordinalFr(n: number): string {
  return n === 1 ? "1er" : `${n}e`;
}

/**
 * Sexe en une lettre. Les chronométreurs publient « H »/« M », « F »/« W » :
 * on ramène aux deux lettres attendues, et on rend tel quel ce qu'on ne
 * reconnaît pas plutôt que d'écraser une valeur exotique.
 */
export function genderShort(gender: string | null | undefined): string {
  if (!gender) return "—";
  const first = gender.trim().toLowerCase()[0];
  if (first === "f" || first === "w") return "F";
  if (first === "m" || first === "h") return "M";
  return gender;
}

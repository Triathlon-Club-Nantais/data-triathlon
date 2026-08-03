import type { Splits } from "@/lib/types";

export interface Segment {
  key: string;
  label: string;
  time: string;
  color: string;
  small?: boolean;
}

export type SchemaEntry = { key: string; label: string; color: string; small?: boolean };

// Échelle catégorielle SPLIT (cf. lib/sport-colors).
const SWIM = "var(--swim)";
const RUN = "var(--run)";
const BIKE = "var(--bike)";
const TRANS = "var(--muted-foreground)"; // transitions T1/T2 en neutre

const SCHEMAS: Record<string, SchemaEntry[]> = {
  duathlon: [
    // Clés alignées sur le backend (mapping.build_splits) : course1/course2.
    { key: "course1", label: "Course 1", color: RUN },
    { key: "t1", label: "T1", color: TRANS, small: true },
    { key: "bike", label: "Vélo", color: BIKE },
    { key: "t2", label: "T2", color: TRANS, small: true },
    { key: "course2", label: "Course 2", color: RUN },
  ],
  "bike-run": [
    { key: "bike", label: "Vélo", color: BIKE },
    { key: "run", label: "Course", color: RUN },
  ],
  aquathlon: [
    { key: "swim", label: "Natation", color: SWIM },
    { key: "run", label: "Course", color: RUN },
  ],
  aquarun: [
    { key: "swim", label: "Natation", color: SWIM },
    { key: "t1", label: "T1", color: TRANS, small: true },
    { key: "run", label: "Course", color: RUN },
  ],
  triathlon: [
    { key: "swim", label: "Natation", color: SWIM },
    { key: "t1", label: "T1", color: TRANS, small: true },
    { key: "bike", label: "Vélo", color: BIKE },
    { key: "t2", label: "T2", color: TRANS, small: true },
    { key: "run", label: "Course", color: RUN },
  ],
};

/** Schéma de segments (clés/libellés/couleurs) adapté au sport. */
export function splitSchema(eventType: string): SchemaEntry[] {
  const type = eventType || "";
  if (type.startsWith("duathlon")) return SCHEMAS.duathlon;
  if (type === "bike-run") return SCHEMAS["bike-run"];
  if (type === "aquathlon") return SCHEMAS.aquathlon;
  if (type === "aquarun") return SCHEMAS.aquarun;
  return SCHEMAS.triathlon;
}

/**
 * Entrée pour un split étiqueté par la **source**, hors de tout schéma de sport.
 *
 * Les scrapers qui renseignent `segments` (ok-time, RaceResult, Chronoplace) clés
 * leurs splits sur les libellés publiés — « NATATION », « COURSE A PIED » —, que
 * `mapping.build_splits` conserve tels quels côté backend : aucune clé canonique
 * à attendre, donc aucun libellé à réécrire. Seule la couleur est devinée du mot,
 * et le neutre couvre ce qu'on ne reconnaît pas plutôt que de mentir.
 */
function sourceEntry(key: string): SchemaEntry {
  const t = key.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  if (/^t\d+$/.test(t) || t.includes("transition")) return { key, label: key, color: TRANS, small: true };
  if (t.includes("nat") || t.includes("swim")) return { key, label: key, color: SWIM };
  if (t.includes("velo") || t.includes("bike") || t.includes("cycl")) return { key, label: key, color: BIKE };
  if (t.includes("course") || t.includes("run") || t.includes("pied") || t.includes("cap"))
    return { key, label: key, color: RUN };
  return { key, label: key, color: TRANS };
}

/** Segments d'une participation : schéma du sport, ou libellés de la source. */
export function splitSegments(
  eventType: string,
  splits: Splits | null | undefined,
): Segment[] {
  if (!splits) return [];
  const attendus = splitSchema(eventType).filter((s) => splits[s.key]);
  if (attendus.length) return attendus.map((s) => ({ ...s, time: splits[s.key] }));
  return Object.entries(splits)
    .filter(([, time]) => time)
    .map(([key, time]) => ({ ...sourceEntry(key), time }));
}

/**
 * Colonnes de splits d'une course : les segments renseignés chez **au moins un**
 * participant. Se base sur l'ensemble complet des participations pour que les
 * colonnes restent stables quand un filtre d'affichage change.
 */
export function splitColumns(
  eventType: string,
  splitsList: (Splits | null | undefined)[],
): SchemaEntry[] {
  const attendus = splitSchema(eventType).filter((s) => splitsList.some((sp) => sp?.[s.key]));
  if (attendus.length) return attendus;
  const vues = new Map<string, SchemaEntry>();
  for (const splits of splitsList) {
    for (const [key, time] of Object.entries(splits ?? {})) {
      if (time && !vues.has(key)) vues.set(key, sourceEntry(key));
    }
  }
  return [...vues.values()];
}

/**
 * Colonnes de splits à partir des seules **clés** publiées par l'épreuve.
 *
 * Même règle que `splitColumns`, mais alimentée par la synthèse d'épreuve
 * plutôt que par les participations affichées (#163) : avec vingt lignes sous
 * la main, déduire les colonnes des lignes les ferait changer d'une page à
 * l'autre. Les clés arrivent dans leur ordre d'apparition, qui fixe celui des
 * colonnes lorsqu'aucun schéma de sport ne s'applique.
 */
export function splitColumnsFromKeys(eventType: string, keys: string[]): SchemaEntry[] {
  const attendus = splitSchema(eventType).filter((s) => keys.includes(s.key));
  if (attendus.length) return attendus;
  return keys.map((key) => sourceEntry(key));
}

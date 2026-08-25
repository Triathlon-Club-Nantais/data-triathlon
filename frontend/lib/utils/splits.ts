import type { Splits } from "@/lib/types";

export interface Segment {
  key: string;
  label: string;
  time: string;
  color: string;
  small?: boolean;
}

type SchemaEntry = { key: string; label: string; color: string; small?: boolean };

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
function splitSchema(eventType: string): SchemaEntry[] {
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

/**
 * Segments d'une participation : schéma du sport pour les clés qu'il connaît,
 * libellés de la source pour les autres — dans **un seul** passage plutôt qu'un
 * filtre suivi d'un repli conditionnel (#563). L'ancienne forme rendait
 * `attendus` dès qu'**une seule** clé du schéma répondait, ce qui écartait en
 * silence les clés **positionnelles** que `mapping.build_splits` pose hors de
 * tout schéma (`segment1` de bike-run, `segment2` de swimrun : leur nommer un
 * sport mentirait, cf. le commentaire de `_SPLIT_KEYS_BY_SPORT`) — le seul
 * chemin qui les aurait rendues (le repli) n'était jamais atteint dès que
 * `bike`/`run` répondaient aussi.
 *
 * Parti pris sur l'ORDRE : on suit celui de `splits` (l'ordre d'insertion de
 * l'objet, garanti par JS pour des clés non numériques), pas un bloc « clés du
 * schéma d'abord, clés supplémentaires ensuite ». `mapping.build_splits`
 * construit ce dict dans l'ordre chronologique du gabarit de sport, donc pour
 * bike-run l'ordre source est déjà segment1 → bike → run : segment1 arrive en
 * tête, comme sur la ligne d'arrivée. Un bloc « schéma puis extra » l'aurait
 * renvoyé en dernier — illisible pour un slot qui se court en premier.
 */
export function splitSegments(
  eventType: string,
  splits: Splits | null | undefined,
): Segment[] {
  if (!splits) return [];
  const schema = new Map(splitSchema(eventType).map((s) => [s.key, s]));
  return Object.entries(splits)
    .filter(([, time]) => time)
    .map(([key, time]) => ({ ...(schema.get(key) ?? sourceEntry(key)), time }));
}

/**
 * Colonnes de splits d'une course : les segments renseignés chez **au moins un**
 * participant. Se base sur l'ensemble complet des participations pour que les
 * colonnes restent stables quand un filtre d'affichage change.
 *
 * Même correctif d'ordre et de repli que `splitSegments` (#563) : une clé du
 * schéma **et** une clé positionnelle hors schéma (bike-run, swimrun) peuvent
 * cohabiter, et le résultat garde l'ordre de première apparition à travers
 * `splitsList` plutôt qu'un bloc schéma-puis-extra — cf. le commentaire de
 * `splitSegments` pour la justification (bike-run : segment1 en tête).
 */
export function splitColumns(
  eventType: string,
  splitsList: (Splits | null | undefined)[],
): SchemaEntry[] {
  const schema = new Map(splitSchema(eventType).map((s) => [s.key, s]));
  const vues = new Map<string, SchemaEntry>();
  for (const splits of splitsList) {
    for (const [key, time] of Object.entries(splits ?? {})) {
      if (time && !vues.has(key)) vues.set(key, schema.get(key) ?? sourceEntry(key));
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
 * l'autre. Les clés arrivent dans leur ordre d'apparition (`keys`), qui fixe
 * celui des colonnes — schéma ou source, même correctif qu'ailleurs (#563).
 */
export function splitColumnsFromKeys(eventType: string, keys: string[]): SchemaEntry[] {
  const schema = new Map(splitSchema(eventType).map((s) => [s.key, s]));
  return keys.map((key) => schema.get(key) ?? sourceEntry(key));
}

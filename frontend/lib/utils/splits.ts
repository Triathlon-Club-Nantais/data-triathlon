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

export function splitSegments(
  eventType: string,
  splits: Splits | null | undefined,
): Segment[] {
  if (!splits) return [];
  return splitSchema(eventType)
    .filter((s) => splits[s.key])
    .map((s) => ({ ...s, time: splits[s.key] }));
}

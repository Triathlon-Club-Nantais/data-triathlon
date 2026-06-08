import type { Splits } from "@/lib/types";

export interface Segment {
  key: string;
  label: string;
  time: string;
  color: string;
  small?: boolean;
}

type SchemaEntry = { key: string; label: string; color: string; small?: boolean };

const SWIM = "#3b82f6";
const RUN = "#10b981";
const BIKE = "#f59e0b";
const TRANS = "#94a3b8";

const SCHEMAS: Record<string, SchemaEntry[]> = {
  duathlon: [
    { key: "swim", label: "Course 1", color: RUN },
    { key: "t1", label: "T1", color: TRANS, small: true },
    { key: "bike", label: "Vélo", color: BIKE },
    { key: "t2", label: "T2", color: TRANS, small: true },
    { key: "run", label: "Course 2", color: RUN },
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

function schemaFor(eventType: string): SchemaEntry[] {
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
  return schemaFor(eventType)
    .filter((s) => splits[s.key])
    .map((s) => ({ ...s, time: splits[s.key] }));
}

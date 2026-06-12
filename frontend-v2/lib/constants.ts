export const EVENT_TYPE_LABELS: Record<string, string> = {
  triathlon: "Triathlon",
  "triathlon-xs": "Triathlon XS",
  "triathlon-s": "Triathlon S",
  "triathlon-m": "Triathlon M",
  "triathlon-l": "Triathlon L",
  "triathlon-xl": "Triathlon XL",
  duathlon: "Duathlon",
  "duathlon-xs": "Duathlon XS",
  "duathlon-s": "Duathlon S",
  "duathlon-m": "Duathlon M",
  "duathlon-l": "Duathlon L",
  swimrun: "SwimRun",
  "swimrun-s": "SwimRun S",
  "swimrun-m": "SwimRun M",
  "swimrun-l": "SwimRun L",
  aquathlon: "Aquathlon",
  aquarun: "Aquarun",
  "bike-run": "Bike & Run",
  "course-a-pied": "Course à pied",
  "course-a-pied-5k": "5 km",
  "course-a-pied-10k": "10 km",
  "course-a-pied-semi": "Semi-marathon",
  "course-a-pied-marathon": "Marathon",
  trail: "Trail",
  cyclisme: "Cyclisme",
  "cyclisme-route": "Cyclisme (route)",
  "cyclisme-clm": "Cyclisme (CLM)",
};

export const EVENT_TYPE_OPTIONS: { value: string; label: string }[] =
  Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => ({ value, label }));

export function eventTypeLabel(type: string | null | undefined): string {
  if (!type) return "";
  return EVENT_TYPE_LABELS[type] ?? type;
}

/** Libellé complet d'une discipline : type + kilométrage si disponible. */
export function disciplineLabel(course: {
  event_type: string | null | undefined;
  distance_km?: number | null;
}): string {
  const label = eventTypeLabel(course.event_type);
  if (course.distance_km) {
    return `${label} · ${course.distance_km} km`;
  }
  return label;
}

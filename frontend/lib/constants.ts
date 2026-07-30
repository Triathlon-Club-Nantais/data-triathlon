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

/** Nom commercial des chronométreurs, dont le slug technique sert de clé en base. */
export const PROVIDER_LABELS: Record<string, string> = {
  klikego: "Klikego",
  breizhchrono: "Breizh Chrono",
  timepulse: "TimePulse",
  wiclax: "Wiclax",
  prolivesport: "ProLiveSport",
  sportinnovation: "Sport Innovation",
  raceresult: "RaceResult",
  chronoplace: "Chronoplace",
  // Competitor est le moteur réel derrière ironman.com (cf. #54) : c'est ce nom
  // que le backend détecte, mais « IRONMAN » est ce que l'utilisateur a collé.
  competitor: "IRONMAN (Competitor)",
  oktime: "OK TIME",
  runnerbreizh: "Runner Breizh",
  // T2Area édite la plateforme, mais c'est la FFTRI qui la sert (`fftri.t2area.com`)
  // et sous ce nom que la fédération y renvoie ses licenciés (cf. #51).
  t2area: "FFTRI (T2Area)",
  // Sporthive est la marque endurance de MYLAPS (cf. #53) — le site s'annonce
  // lui-même « MYLAPS Sporthive ». Sans cette entrée le badge affiche le slug
  // brut : la table ne dit rien du support, elle ne fait que traduire un nom.
  sporthive: "MYLAPS Sporthive",
  chronoweb: "ChronoWeb",
};

/** Libellé d'un chronométreur ; le slug brut à défaut, « Source » si non renseigné. */
export function providerLabel(provider: string | null | undefined): string {
  if (!provider) return "Source";
  return PROVIDER_LABELS[provider] ?? provider;
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

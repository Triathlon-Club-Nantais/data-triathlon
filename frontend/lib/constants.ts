const EVENT_TYPE_LABELS: Record<string, string> = {
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
  "duathlon-xl": "Duathlon XL",
  swimrun: "SwimRun",
  "swimrun-s": "SwimRun S",
  "swimrun-m": "SwimRun M",
  "swimrun-l": "SwimRun L",
  aquathlon: "Aquathlon",
  "aquathlon-xs": "Aquathlon XS",
  "aquathlon-s": "Aquathlon S",
  "aquathlon-m": "Aquathlon M",
  "aquathlon-l": "Aquathlon L",
  "aquathlon-xl": "Aquathlon XL",
  aquarun: "Aquarun",
  "bike-run": "Bike & Run",
  // Nouvelles disciplines de la saisie manuelle (#270).
  "swim-bike": "Swim Bike",
  "swim-bike-xs": "Swim Bike XS",
  "swim-bike-s": "Swim Bike S",
  "swim-bike-m": "Swim Bike M",
  "swim-bike-l": "Swim Bike L",
  "swim-bike-xl": "Swim Bike XL",
  "cross-triathlon": "Cross Triathlon",
  "raid-multisport": "Raid Multisport",
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

/**
 * Disciplines fédérales proposées par le formulaire de saisie manuelle
 * (#270), dans l'ordre demandé par le porteur produit. « Run & Bike » y est
 * confirmé comme la discipline déjà connue sous `bike-run` (« Bike & Run ») —
 * une seule et même entrée, pas deux.
 */
export const MANUAL_ENTRY_DISCIPLINES: { value: string; label: string }[] = [
  { value: "triathlon", label: "Triathlon" },
  { value: "duathlon", label: "Duathlon" },
  { value: "swimrun", label: "Swim & Run" },
  { value: "bike-run", label: "Bike & Run" },
  { value: "raid-multisport", label: "Raid Multisport" },
  { value: "cross-triathlon", label: "Cross Triathlon" },
  { value: "aquathlon", label: "Aquathlon" },
  { value: "swim-bike", label: "Swim Bike" },
];

/** Disciplines dont le format se précise en second temps (FR-007). */
export const MANUAL_ENTRY_DISCIPLINES_WITH_FORMAT: ReadonlySet<string> = new Set([
  "triathlon",
  "duathlon",
  "aquathlon",
  "swim-bike",
]);

export const MANUAL_ENTRY_FORMATS: { value: string; label: string }[] = [
  { value: "xs", label: "XS" },
  { value: "s", label: "S" },
  { value: "m", label: "M" },
  { value: "l", label: "L" },
  { value: "xl", label: "XL" },
  { value: "autre", label: "Autre" },
];

/**
 * Champs de temps pertinents par discipline (encart temps du formulaire
 * manuel, FR-015). Chaque entrée est une clé de `ScrapedPreview`
 * (`swim_time`/`t1_time`/`bike_time`/`t2_time`/`run_time`) associée au
 * libellé à afficher — le nom du champ transmis à l'API ne change jamais,
 * seul son intitulé s'adapte (ex. duathlon : les deux courses à pied
 * réutilisent les slots `swim_time`/`run_time`, cf. `services/mapping.py`
 * côté backend).
 */
export const MANUAL_ENTRY_TIME_FIELDS: Record<
  string,
  { key: "swim_time" | "t1_time" | "bike_time" | "t2_time" | "run_time"; label: string }[]
> = {
  triathlon: [
    { key: "swim_time", label: "Natation" },
    { key: "t1_time", label: "T1" },
    { key: "bike_time", label: "Vélo" },
    { key: "t2_time", label: "T2" },
    { key: "run_time", label: "Course à pied" },
  ],
  duathlon: [
    { key: "swim_time", label: "1ère course à pied" },
    { key: "t1_time", label: "T1" },
    { key: "bike_time", label: "Vélo" },
    { key: "t2_time", label: "T2" },
    { key: "run_time", label: "2ème course à pied" },
  ],
  swimrun: [
    { key: "swim_time", label: "Natation" },
    { key: "bike_time", label: "Segment intermédiaire" },
    { key: "run_time", label: "Course à pied" },
  ],
  "bike-run": [
    { key: "bike_time", label: "Vélo" },
    { key: "run_time", label: "Course à pied" },
  ],
  aquathlon: [
    { key: "swim_time", label: "Natation" },
    { key: "t1_time", label: "T1" },
    { key: "run_time", label: "Course à pied" },
  ],
  "swim-bike": [
    { key: "swim_time", label: "Natation" },
    { key: "t1_time", label: "T1" },
    { key: "bike_time", label: "Vélo" },
  ],
  "cross-triathlon": [
    { key: "swim_time", label: "Natation" },
    { key: "t1_time", label: "T1" },
    { key: "bike_time", label: "Vélo" },
    { key: "t2_time", label: "T2" },
    { key: "run_time", label: "Course à pied" },
  ],
  // Raid Multisport : aucun découpage prévisible (cf. data-model.md §6),
  // absent de cette table → l'encart n'affiche que le temps total.
};

export const EVENT_TYPE_OPTIONS: { value: string; label: string }[] =
  Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => ({ value, label }));

export function eventTypeLabel(type: string | null | undefined): string {
  if (!type) return "";
  return EVENT_TYPE_LABELS[type] ?? type;
}

/** Nom commercial des chronométreurs, dont le slug technique sert de clé en base. */
const PROVIDER_LABELS: Record<string, string> = {
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
  chronoweb: "Chronoweb",
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

/**
 * Libellés **français** des codes d'échec du parcours de connexion (#114).
 *
 * Le backend n'émet qu'un code appartenant à un ensemble fermé — jamais un
 * message du fournisseur, jamais une donnée d'entrée. La traduction vit donc
 * ici, sur le modèle de PROVIDER_LABELS.
 */
const AUTH_ERROR_LABELS: Record<string, string> = {
  state_mismatch:
    "Votre demande de connexion a expiré ou n'a pas pu être vérifiée. Merci de recommencer.",
  email_unverified:
    "Votre fournisseur ne certifie aucune adresse e-mail vérifiée pour ce compte.",
  account_not_allowed:
    "Cette adresse n'est pas autorisée à accéder à l'espace contributeur.",
  provider_error: "La connexion a été refusée ou interrompue. Merci de réessayer.",
  provider_unavailable:
    "Le service de connexion est momentanément injoignable. Merci de réessayer plus tard.",
};

/**
 * Un code inconnu retombe sur un message générique et n'est **jamais** rendu
 * verbatim : la page de connexion ne doit pas devenir un point d'injection.
 */
export function authErrorLabel(code: string | null | undefined): string {
  if (!code) return "";
  return AUTH_ERROR_LABELS[code] ?? "La connexion a échoué. Merci de réessayer.";
}

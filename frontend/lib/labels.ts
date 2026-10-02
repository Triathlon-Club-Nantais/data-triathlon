import type { RankType } from "@/lib/rank";
import type { PodiumScope } from "@/lib/podium-scope";
import type { Feedback } from "@/lib/types";

/**
 * Libellés utilisateur du vocabulaire de rang. Une seule source pour les trois
 * sites d'affichage — toggle (RankTypeToggle), delta des StatCard (StatCardsRank),
 * badge de podium (PodiumsList) — cf. #133. Un renommage (« Genre » → « Sexe »)
 * ne touche plus qu'ici.
 *
 * `scratch` (mode du toggle) et `overall` (scope résultant d'un podium) désignent
 * la même chose vue de deux côtés : le rang général. Ils rendent donc **le même
 * libellé** (« Général »).
 */

const RANK_LABEL_SHORT: Record<RankType, string> = {
  scratch: "Général",
  category: "Catégorie",
  gender: "Genre",
  all: "Tous",
};

// Forme minuscule utilisée en `delta` sous les compteurs (« 12 · général »).
const RANK_LABEL_LONG: Record<RankType, string> = {
  scratch: "général",
  category: "catégorie",
  gender: "genre",
  all: "général, genre ou catégorie",
};

export function rankTypeLabel(
  t: RankType,
  opts?: { form?: "short" | "long" },
): string {
  return opts?.form === "long" ? RANK_LABEL_LONG[t] : RANK_LABEL_SHORT[t];
}

const SCOPE_LABEL: Record<PodiumScope, string> = {
  overall: RANK_LABEL_SHORT.scratch,
  gender: RANK_LABEL_SHORT.gender,
  category: RANK_LABEL_SHORT.category,
};

export function podiumScopeLabel(s: PodiumScope): string {
  return SCOPE_LABEL[s];
}

/**
 * Libellés des statuts de participation (#1084) : la saisie manuelle, le badge
 * de résultat et les compteurs de l'épreuve disent le même mot, dans la même
 * graphie. Les valeurs sont celles de l'API, jamais traduites côté backend.
 *
 * Deux usages, pas le singulier et le pluriel d'un même mot : `one` est
 * **l'état** d'une participation (option de saisie, titre du badge : « Arrivé »,
 * « Non partant », graphies arrêtées par la décision de #1084), `many` l'intitulé
 * d'un **compteur** (« Arrivants », « Non-partants »). `unit` est le nom compté
 * au singulier, pour les phrases à nombre (`participationStatusCount`).
 */
export const PARTICIPATION_STATUSES = ["finisher", "DNF", "DNS", "DSQ"] as const;
export type ParticipationStatus = (typeof PARTICIPATION_STATUSES)[number];

const STATUS_LABEL: Record<ParticipationStatus, { one: string; many: string; unit: string }> = {
  finisher: { one: "Arrivé", many: "Arrivants", unit: "arrivant" },
  DNF: { one: "Abandon", many: "Abandons", unit: "abandon" },
  DNS: { one: "Non partant", many: "Non-partants", unit: "non-partant" },
  DSQ: { one: "Disqualifié", many: "Disqualifiés", unit: "disqualifié" },
};

/** « 1 arrivant », « 2 non-partants » : le nom compté, accordé au nombre. */
export function participationStatusCount(status: ParticipationStatus, n: number): string {
  const { many, unit } = STATUS_LABEL[status];
  return `${n} ${n > 1 ? many.toLocaleLowerCase("fr") : unit}`;
}

export function participationStatusLabel(
  status: ParticipationStatus,
  opts?: { form?: "one" | "many" },
): string {
  return STATUS_LABEL[status][opts?.form ?? "one"];
}

/** Statut d'un retour utilisateur : la file des retours et le journal le disent pareil. */
export const FEEDBACK_STATUS_LABELS: Record<Feedback["status"], string> = {
  nouveau: "Nouveau",
  en_cours: "En cours",
  traite: "Traité",
  ignore: "Ignoré",
};

/**
 * Nom commercial des chronométreurs, dont le slug technique sert de clé en base
 * (#636). Seule source côté front de ce vocabulaire.
 */
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
  // Sporthive est la marque endurance de MYLAPS (cf. #53), le site s'annonce
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

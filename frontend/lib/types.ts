// Miroir des schémas Pydantic backend. Source de vérité : app/schemas/*.py.

export interface AthleteBrief {
  id: number;
  nom: string;
  prenom: string;
  gender: string;
  club: string | null;
}

export interface CourseBrief {
  id: number;
  name: string;
  event_date: string | null; // ISO date "YYYY-MM-DD"
  event_type: string;
  provider: string;
  source_url: string;
  is_relay: boolean;
  distance_km?: number | null;
  // Indice de fiabilité calculé à l'import ; null = course jamais évaluée.
  is_reliable?: boolean | null;
  quality_issues?: Record<string, number> | null;
}

// Clés possibles de splits : "swim" | "t1" | "bike" | "t2" | "run"
export type Splits = Record<string, string>;

export interface Participation {
  id: number;
  athlete: AthleteBrief;
  course: CourseBrief;
  club: string | null;
  /** Appartenance au club, tranchée par le backend (jamais recalculée ici). */
  is_tcn: boolean;
  category: string | null;
  bib_number: string | null;
  rank_overall: number | null;
  rank_category: number | null;
  rank_gender: number | null;
  total_time: string | null;
  status: string;
  is_relay: boolean;
  splits: Splits | null;
  created_at: string | null;
  // Nombre de finishers classés de la course (même groupe solo/relais).
  // Servi par la seule route /athletes/{id} — d'où l'optionnalité.
  course_finishers?: number | null;
}

export interface EventOut {
  id: number; // course_id — sert à charger les participants au dépliage
  event_name: string;
  event_date: string | null;
  event_type: string;
  is_relay: boolean;
  distance_km?: number | null;
  total: number;
  tcn_count: number;
}

export interface EventPage {
  items: EventOut[];
  total_events: number;
  total_participations: number;
}

export interface GeoEvent {
  event_name: string;
  event_date: string | null;
  event_type: string;
  count: number;
  tcn_count: number;
  lat: number;
  lon: number;
}

export interface RecentItem {
  id: number;
  athlete_name: string;
  athlete_firstname: string;
  club: string;
  event_name: string;
  event_type: string;
  event_date: string | null;
  total_time: string;
  scraped_at: string | null;
}

export interface Stats {
  total: number;
  athletes: number;
  events: number;
  by_type: Record<string, number>;
  by_month: Record<string, number>;
  recent: RecentItem[];
}

// Saison sportive disponible (miroir de SeasonOut backend).
export interface Season {
  start_year: number;
  label: string;
  event_count: number;
  participation_count: number;
  is_current: boolean;
}

// Forme plate renvoyée par POST /scrape et attendue par POST /participations.
export interface ScrapedPreview {
  provider: string;
  source_url: string;
  athlete_name: string;
  athlete_firstname: string;
  club: string;
  category: string;
  gender: string;
  bib_number: string;
  event_name: string;
  event_date: string | null;
  event_type: string;
  rank_overall: number | null;
  rank_category: number | null;
  rank_gender: number | null;
  total_time: string;
  swim_time: string;
  t1_time: string;
  bike_time: string;
  t2_time: string;
  run_time: string;
  is_relay: boolean;
  raw_data: Record<string, unknown>;
}

// Une course touchée par un import (heat, épreuve d'un multi-événement…).
// Émis par le SSE `done` et par `POST /scrape/event` — sert à câbler
// « Voir les résultats » sur /ajouter (#135).
export interface ImportedCourse {
  id: number;
  name: string;
  event_type: string;
  is_relay?: boolean;
}

// Un heat en échec pendant un fan-out Klikego (#156).
export interface HeatFailure {
  heat_slug: string;
  reason: string;
}

export interface ImportResult {
  imported: number;
  updated: number;
  skipped: number;
  cached?: boolean;
  courses: ImportedCourse[];
  // Compteurs fan-out (#156) — présents pour tous les providers ; 0/[] hors Klikego.
  heats_enumerated?: number;
  heats_imported?: number;
  heats_cached?: number;
  heats_failed?: number;
  failures?: HeatFailure[];
}

// Événements du flux SSE d'import.
// Fan-out Klikego (#156) : la phase `scraping` peut porter une progression par
// heat (`heat_index`/`heats_total`/`heat_slug`/`heat_label`). Ces clés sont
// optionnelles — un provider mono-course émet le seul yield initial avec
// `message`, sans elles.
export type ImportProgressEvent =
  | {
      phase: "scraping";
      message?: string;
      heat_index?: number;
      heats_total?: number;
      heat_slug?: string;
      heat_label?: string;
    }
  | { phase: "saving"; total: number; imported: number; updated: number; skipped: number; progress: number }
  | {
      phase: "done";
      imported: number;
      updated: number;
      skipped: number;
      total: number;
      cached?: boolean;
      courses: ImportedCourse[];
      // Fan-out (#156) — 5 clés rétro-compatibles.
      heats_enumerated?: number;
      heats_imported?: number;
      heats_cached?: number;
      heats_failed?: number;
      failures?: HeatFailure[];
    }
  | { phase: "error"; message: string };

export interface PendingProvider {
  id: number;
  url: string;
  provider_hint: string;
  reported_at: string | null;
}

export interface AthleteDetail {
  athlete: AthleteBrief;
  participations: Participation[];
}

export interface CourseDetail {
  course: CourseBrief;
  /** La tranche demandée, déjà dans l'ordre d'affichage — ne pas la retrier. */
  participations: Participation[];
  /** Total de la **sélection** (recherche + portée club), pas de l'épreuve. */
  total: number;
  page: number;
  /** `null` quand tout le classement a été demandé (`page_size=all`). */
  page_size: number | null;
}

/** Paramètres de lecture d'un classement d'épreuve (#163). */
export interface CourseQuery {
  page?: number;
  /** Entier, ou « all » pour le classement entier en une page. */
  page_size?: number | "all";
  /** Recherche sur le nom ou le prénom de l'athlète. */
  q?: string;
  scope?: "club";
}

export interface CategoryCount {
  name: string;
  count: number;
}

export interface ClubCount {
  name: string;
  count: number;
  is_tcn: boolean;
}

export interface Histogram {
  bars: number[];
  start_sec: number;
  bucket_sec: number;
}

/**
 * Synthèse d'une épreuve **entière**, calculée par le backend (#163).
 *
 * Indépendante de la recherche et de la portée club en cours : c'est ce qui
 * garantit que chercher un nom ne fait pas tomber l'histogramme à une barre.
 */
export interface CourseSummary {
  total: number;
  finishers: number;
  non_finishers: number;
  unknown: number;
  tcn_count: number;
  male: number;
  female: number;
  categories: CategoryCount[];
  /** Somme sur **toutes** les catégories : dénominateur des pourcentages,
   *  et non la somme des 8 rendues — qui gonflerait chaque barre. */
  categories_total: number;
  clubs: ClubCount[];
  histogram: Histogram | null;
  /** Colonnes de temps intermédiaires du tableau — stables d'une page à l'autre. */
  split_keys: string[];
}

export interface ParticipationFilters {
  name?: string;
  event_type?: string;
  event_name?: string;
  scope?: "club";
  federal_only?: boolean;
  date_from?: string;
  date_to?: string;
  seasons?: number[];
  course_id?: number;
  sort?: string; // "date_desc" | "date_asc" | "name" (épreuves)
  page?: number;
  page_size?: number;
}

// ── Authentification (#114) ──────────────────────────────────────────────────

/** Un moyen de connexion proposé par le backend. Aucun n'est codé en dur ici. */
export interface AuthMethod {
  slug: string;
  label: string;
}

/** Identité de la session courante, rendue par `GET /auth/me`. */
export interface SessionRole {
  id: number;
  slug: string;
  name: string;
  organisation_id: number | null;
}

export interface SessionUser {
  id: number;
  email: string;
  display_name: string;
  created_at: string;
  /**
   * Codes des pouvoirs effectifs (#115) — « ai-je le droit d'afficher ce
   * bouton ». Vide pour un connecté sans rôle, qui est un état légitime.
   */
  permissions: string[];
  /**
   * Rôles portés — « comment me présenter à moi-même ». Ne se déduit pas de
   * `permissions` : sans lui, écrire « connecté en tant qu'administrateur »
   * exigerait un appel de plus, que `GET /admin/roles` refuserait à qui n'a pas
   * `roles:read`.
   */
  roles: SessionRole[];
}

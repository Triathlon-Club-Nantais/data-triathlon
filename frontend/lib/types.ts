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
}

// Clés possibles de splits : "swim" | "t1" | "bike" | "t2" | "run"
export type Splits = Record<string, string>;

export interface Participation {
  id: number;
  athlete: AthleteBrief;
  course: CourseBrief;
  club: string | null;
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

export interface ImportResult {
  imported: number;
  skipped: number;
  cached?: boolean;
}

// Événements du flux SSE d'import.
export type ImportProgressEvent =
  | { phase: "scraping"; message: string }
  | { phase: "saving"; total: number; imported: number; skipped: number; progress: number }
  | { phase: "done"; imported: number; skipped: number; total: number; cached?: boolean }
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
  participations: Participation[];
}

export interface ParticipationFilters {
  name?: string;
  event_type?: string;
  event_name?: string;
  club?: string;
  date_from?: string;
  date_to?: string;
  seasons?: number[];
  course_id?: number;
  sort?: string; // "date_desc" | "date_asc" | "name" (épreuves)
  page?: number;
  page_size?: number;
}

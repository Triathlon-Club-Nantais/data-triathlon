// Miroir des schémas Pydantic backend. Source de vérité : app/schemas/*.py.

export interface AthleteBrief {
  id: number;
  nom: string;
  prenom: string;
  gender: string;
  club: string | null;
}

// Miroir de AthleteSeasonActivity backend (#274, #709) — athlète + ses
// compteurs d'épreuves sur la saison filtrée. Pas de `club` : la route qui
// l'expose est déjà scopée club côté appelant. `participation_count` reste
// égal à `club_affiliated_count` (compat, additif seulement).
export interface AthleteSeasonActivity {
  id: number;
  nom: string;
  prenom: string;
  participation_count: number;
  total_count: number;
  validated_count: number;
  club_affiliated_count: number;
  season_validated: boolean | null;
}

// Miroir de AthleteSearchResult backend (#484) — recherche classée par
// pertinence pour la palette ⌘K. `club` en plus de AthleteSeasonActivity :
// affiché sous le nom dans la palette, comme `AthleteBrief.club` l'était déjà.
export interface AthleteSearchResult {
  id: number;
  nom: string;
  prenom: string;
  gender: string;
  club: string | null;
  participation_count: number;
}

export interface CourseBrief {
  id: number;
  name: string;
  event_date: string | null; // ISO date "YYYY-MM-DD"
  event_type: string;
  provider: string;
  source_url: string;
  is_relay: boolean;
  // Précision libre du format (« Autre » du formulaire manuel, #270).
  format_label?: string | null;
  distance_km?: number | null;
  // Indice de fiabilité calculé à l'import ; null = course jamais évaluée.
  is_reliable?: boolean | null;
  quality_issues?: Record<string, number> | null;
}

/** Les trois verdicts d'une épreuve, rendus par `PATCH …/reliability` (#115). */
export interface CourseReliability {
  id: number;
  is_reliable: boolean | null;
  is_reliable_computed: boolean | null;
  reliability_override: boolean | null;
  quality_issues: Record<string, number> | null;
}

// Clés possibles de splits : "swim" | "t1" | "bike" | "t2" | "run"
export type Splits = Record<string, string>;

/** Une étape du graphique d'évolution du classement. */
export interface RankingEvolutionStep {
  segment: string;
  scratch_position: number;
  segment_position: number;
  /** Temps cumulé de l'athlète à la sortie de l'étape, en secondes (US5, #466). */
  cumulative_seconds?: number | null;
}

/** Comparaison de l'athlète au coureur occupant une position de référence. */
export interface ComparisonRow {
  position_label: string;
  rank: number;
  /** Par clé de segment, plus « total » : temps de l'athlète en % de la référence. */
  percentages: Record<string, number>;
  /** Mêmes clés que `percentages` : écart brut en secondes (US4, #466). */
  mine_seconds?: Record<string, number>;
  theirs_seconds?: Record<string, number>;
}

/** Places scratch gagnées si un segment avait été amélioré d'un pourcentage donné. */
export interface ImprovementRow {
  segment: string;
  gains: Record<string, number>;
}

export interface ParticipationStats {
  /**
   * Segments publiés par l'épreuve, dans l'ordre d'affichage. Porté par
   * l'enveloppe et non déduit des blocs : ceux-ci omettent les valeurs
   * manquantes, et une colonne s'y déduirait alors de son absence.
   */
  segments: string[];
  ranking_evolution: RankingEvolutionStep[];
  comparison: ComparisonRow[];
  improvement: ImprovementRow[];
}

export interface Participation {
  id: number;
  /**
   * **Toujours servi** — se lit sans `?.` (#593, jumeau de #578 sur `course`).
   * `participations.athlete_id` est `NOT NULL` depuis le schéma initial,
   * `ParticipationOut.athlete` est requis côté Pydantic (une relation absente y
   * ferait un 500, jamais une réponse amputée), et la relation est chargée en
   * `joinedload`/`contains_eager` par les routes qui la servent.
   *
   * En revanche `prenom` et `gender` valent `""` par défaut côté backend,
   * jamais `null` : les `filter(Boolean)` qui les entourent, eux, servent.
   */
  athlete: AthleteBrief;
  /**
   * **Toujours servie** — se lit sans `?.` (#578). Trois maillons le
   * garantissent : `participations.course_id` est `NOT NULL` depuis le schéma
   * initial, `ParticipationOut.course` est requis côté Pydantic (une relation
   * absente y ferait un 500, jamais une réponse amputée), et la relation est
   * chargée en `joinedload`/`contains_eager` par toutes les routes.
   *
   * Le code la lisait pourtant en optionnel partout : le typage décrivait alors
   * autre chose que le programme, et les `?.` masquaient les vraies absences au
   * lieu de les signaler.
   */
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
  team_name?: string | null;
  evidence_url?: string | null;
  // Résultat déclaré non encore vérifié par un bénévole (#270, #271).
  is_pending_validation?: boolean;
  // Écarté par un bénévole comme non conforme (#437).
  is_rejected?: boolean;
  splits: Splits | null;
  // Écart relatif **signé** entre `total_time` et la somme des inters :
  // `(total − Σ inters) / total`. Calculé par le serveur, jamais ici — la
  // médiane de l'épreuve porte sur toutes les lignes, et deux implémentations
  // de la même règle divergeraient (#76, #486). `null` quand la ligne n'est pas
  // évaluable : relais, splits absents, schéma incomplet, temps illisible.
  split_gap_ratio?: number | null;
  created_at: string | null;
  // Nombre de finishers classés de la course (même groupe solo/relais).
  // Servi par la seule route /athletes/{id} — d'où l'optionnalité.
  course_finishers?: number | null;
  // Statistiques détaillées, peuplées par la seule route /participations/{id}.
  // `null` quand la course n'est pas éligible ou que la participation est un
  // relais : c'est ce null qui pilote l'état « statistiques indisponibles ».
  stats?: ParticipationStats | null;
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
  // Miroir des deux champs de `CourseBrief` : sans eux, la liste ne peut pas
  // marquer ce qu'elle liste sans un second appel (#486). `null` = épreuve
  // jamais évaluée, état normal des imports antérieurs au calcul.
  is_reliable?: boolean | null;
  quality_issues?: Record<string, number> | null;
}

export interface EventPage {
  items: EventOut[];
  total_events: number;
  total_participations: number;
}

export interface ValidationQueueBacklogPoint {
  date: string;
  pending_count: number;
}

export interface ValidationQueueHistory {
  backlog_by_day: ValidationQueueBacklogPoint[];
  average_resolution_seconds: number | null;
}

export interface GeoEvent {
  course_id: number;
  event_name: string;
  event_date: string | null;
  event_type: string;
  count: number;
  tcn_count: number;
  lat: number;
  lon: number;
}

interface RecentItem {
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

export interface RankCountersBucket {
  victories: number;
  podiums: number;
  top10: number;
}

export interface DashboardRankCounters {
  scratch: RankCountersBucket;
  category: RankCountersBucket;
  all: RankCountersBucket;
  gender: { women: RankCountersBucket; men: RankCountersBucket };
}

export interface Stats {
  total: number;
  athletes: number;
  events: number;
  by_type: Record<string, number>;
  by_month: Record<string, number>;
  recent: RecentItem[];
  rank_counters: DashboardRankCounters;
}

// Miroir de ClubRosterEntry/ClubPodiumEntry/ClubPodiums/ClubSummary backend (#581).
export interface ClubRosterEntry {
  athlete_id: number;
  prenom: string;
  nom: string;
  count: number;
  podiums: number;
  podiums_overall: number;
  podiums_gender: number;
  podiums_category: number;
}

export interface ClubPodiumEntry {
  participation_id: number;
  athlete_id: number;
  athlete_name: string;
  event_name: string;
  event_type: string;
  is_relay: boolean;
  event_date: string | null;
  rank: number;
  scope: "overall" | "gender" | "category";
  total_time: string | null;
}

export interface ClubPodiums {
  scratch: ClubPodiumEntry[];
  category: ClubPodiumEntry[];
  gender: ClubPodiumEntry[];
  all: ClubPodiumEntry[];
}

// Miroir de DisciplinePodiumCounts/ClubComposition/ClubRosterRank backend (#642, #641).
export interface DisciplinePodiumCounts {
  overall: number;
  gender: number;
  category: number;
  all: number;
}

export interface ClubComposition {
  gender: Record<string, number>;
  category: Record<string, number>;
}

export interface ClubSummary {
  roster: ClubRosterEntry[];
  podiums: ClubPodiums;
  podiums_by_discipline: Record<string, DisciplinePodiumCounts>;
  composition: ClubComposition;
}

export interface ClubRosterRank {
  rank: number;
  total: number;
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
  // Précision libre du format (« Autre ») ou distance totale des disciplines
  // sans format normalisé (#270).
  format_label: string;
  distance_km: number | null;
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
  status: string;
  team_name: string;
  evidence_url: string;
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
// Phase C Klikego (#583) : `detail_done`/`detail_total` portent en plus la
// progression **dans** le heat en cours (participants dont la page détail a
// été récupérée) — sans elles, un gros heat restait figé plusieurs minutes
// entre deux events par heat.
export type ImportProgressEvent =
  | {
      phase: "scraping";
      message?: string;
      heat_index?: number;
      heats_total?: number;
      heat_slug?: string;
      heat_label?: string;
      detail_done?: number;
      detail_total?: number;
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

/**
 * Une adresse autorisée à ouvrir une session (#170).
 *
 * `created_by_name` est un nom d'affichage, pas un identifiant : il est `null`
 * quand l'inscription vient de la CLI d'amorçage ou de la reprise de production.
 */
export interface AllowedEmail {
  id: number;
  email: string;
  created_at: string;
  created_by_name: string | null;
  /**
   * Le rôle que portera le compte **à sa création** (#239) — `null` quand
   * l'adresse n'en donne aucun, ce qui reste le cas ordinaire. Sans lui,
   * autoriser et attribuer étaient deux gestes séparés par la première
   * connexion de la personne, qu'un administrateur ne contrôle pas.
   */
  role: SessionRole | null;
  /**
   * Cette adresse porte-t-elle au moins un compte ? `false` = autorisée, jamais
   * venue — et le rôle ci-dessus attend donc toujours d'être appliqué.
   */
  has_account: boolean;
}

/**
 * État courant du mot de passe partagé bénévoles
 * (`specs/20260815-173645-admin-mdp-benevoles/`) — **jamais** le mot de passe
 * ni son empreinte.
 */
export interface BenevoleAccessConfig {
  configured: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

/**
 * Réponse de la génération sécurisée — la **seule** forme qui porte jamais un
 * mot de passe en clair, et une seule fois (FR-003).
 */
export interface BenevoleAccessGenerated {
  password: string;
  updated_at: string;
  updated_by: string;
}

/** État courant du mot de passe partagé du site (#509) — jamais le mot de
 * passe ni son empreinte. */
export interface SiteAccessConfig {
  configured: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

/** Réponse de la génération sécurisée — la seule forme qui porte jamais un
 * mot de passe en clair, une seule fois. */
export interface SiteAccessGenerated {
  password: string;
  updated_at: string;
  updated_by: string;
}

/** Les deux natures d'entrée de la portée des compteurs (#95), telles
 * qu'elles s'écrivent dans l'URL. */
export type ScopeKind = "disciplines" | "club-labels";

/** Une entrée de la portée des compteurs — une chaîne, et sa provenance. */
export interface CounterScopeEntry {
  id: number;
  /** La forme comparable : c'est elle qui est comparée, donc c'est elle qu'on
   * affiche. La casse saisie n'est pas conservée. */
  value: string;
  /** Pour une discipline : le slug appartient-il à la nomenclature ? Porte
   * l'avertissement. Toujours `true` pour un libellé de club. */
  is_known: boolean;
  created_at: string;
  /** `null` pour les entrées d'amorçage — rendues « Configuration initiale ». */
  created_by: string | null;
}

/** Les deux listes qui bornent les compteurs (#95). */
export interface CounterScope {
  disciplines: CounterScopeEntry[];
  club_labels: CounterScopeEntry[];
}

/** Une variante de libellé rattachée à un nom canonique affiché (#635). */
export interface ClubAlias {
  id: number;
  canonical_name: string;
  /** La forme normalisée du libellé brut — casse et espaces aplatis. */
  alias: string;
  created_at: string;
  created_by: string | null;
}

export interface ClubAliasList {
  entries: ClubAlias[];
}

/**
 * Un rôle et sa composition (#115).
 *
 * `stale_permissions` liste les codes présents en base mais absents de
 * l'inventaire de l'application : inertes, purgeables, jamais bloquants.
 * `is_system` marque un rôle livré avec l'application : sa composition se
 * modifie comme celle des autres (FR-006), seule sa **suppression** est refusée.
 */
export interface Role {
  id: number;
  organisation_id: number | null;
  slug: string;
  name: string;
  description: string;
  is_system: boolean;
  is_superuser: boolean;
  permissions: string[];
  stale_permissions: string[];
  holders: number;
}

/**
 * Un groupe d'appartenance (#197).
 *
 * **Ni `permissions`, ni `is_superuser`** — et ce n'est pas une omission : un
 * groupe dit à quoi on appartient, un rôle ce qu'on peut faire. La garde
 * d'autorisation ne lit jamais un groupe.
 */
export interface Group {
  id: number;
  organisation_id: number;
  slug: string;
  name: string;
  description: string;
  member_count: number;
  created_at: string;
}

/**
 * Un membre d'un groupe.
 *
 * `is_active: false` est un compte désactivé (#170) : il **reste** membre, rien
 * de ce que porte un groupe ne dépendant de son activité.
 */
export interface GroupMember {
  user_id: number;
  email: string;
  display_name: string;
  is_active: boolean;
  joined_at: string;
}

/** Un groupe **et sa composition** — ce que rendent les cinq gestes ciblés. */
export interface GroupDetail extends Group {
  members: GroupMember[];
}

/**
 * Un utilisateur vu depuis l'administration (#115).
 *
 * `is_active: false` est l'effet d'un retrait de la liste d'autorisation
 * (#170) : le compte survit, ses rôles aussi, mais il n'ouvre plus de session.
 * `roles` porte le même DTO que `SessionRole` — `RoleBrief` côté API.
 */
export interface AdminUser {
  id: number;
  email: string;
  display_name: string;
  is_active: boolean;
  roles: SessionRole[];
  created_at: string;
}

export interface AthleteDetail {
  athlete: AthleteBrief;
  participations: Participation[];
}

/** Une ligne de `GET /courses/{id}/sources` — miroir de `CourseSourceOut` (#284). */
export interface CourseSource {
  id: number;
  url: string;
  provider: string;
  is_active: boolean;
  last_scraped_at: string | null;
}

// Événements du flux SSE de `POST /admin/courses/{id}/rescrape` (#118).
// Même famille que `ImportProgressEvent`, mais `done` porte `orphans_removed`
// (propre à ce geste — cf. contracts/admin-rescrape-sse.md) et aucune clé
// fan-out (le re-scrape cible la source active, pas un provider mono-course
// forcément Klikego).
export type RescrapeProgressEvent =
  | { phase: "scraping"; message?: string; heat_index?: number; heats_total?: number; heat_slug?: string; heat_label?: string }
  | { phase: "saving"; total: number; imported: number; updated: number; skipped: number; progress: number }
  | {
      phase: "done";
      imported: number;
      updated: number;
      skipped: number;
      reconciled: number;
      total: number;
      orphans_removed: number;
    }
  | { phase: "error"; message: string };

// Événements du flux SSE de `PATCH /admin/courses/{id}/sources/{sourceId}`
// (#285, #624) — même mécanisme que `RescrapeProgressEvent`, mais `done` porte
// les compteurs d'un **remplacement total** (pas un upsert) et la liste des
// sources à jour, dans la forme de `GET /courses/{id}/sources` (#284) : elle
// remplace l'ancien corps JSON de la réponse, pour que l'écran se réaffiche
// sans second appel.
export type SwitchSourceProgressEvent =
  | { phase: "scraping"; message?: string; heat_index?: number; heats_total?: number; heat_slug?: string; heat_label?: string }
  | { phase: "saving"; total: number }
  | {
      phase: "done";
      participations_deleted: number;
      participations_imported: number;
      athletes_purged: number;
      sources: CourseSource[];
    }
  | { phase: "error"; message: string };

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
  /** Libellé **exact** d'un club, tel que rendu par `/summary` (#486). */
  club?: string;
  /** Code **exact** de catégorie, tel que rendu par `/summary` (#486). */
  category?: string;
}

interface CategoryCount {
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
  /** Ventilation de `non_finishers` par statut (#331) : `dnf + dns + dsq === non_finishers`. */
  dnf: number;
  dns: number;
  dsq: number;
  unknown: number;
  tcn_count: number;
  male: number;
  female: number;
  categories: CategoryCount[];
  /** Somme sur **toutes** les catégories : dénominateur des pourcentages,
   *  et non la somme des 8 rendues — qui gonflerait chaque barre. */
  categories_total: number;
  clubs: ClubCount[];
  /** Nombre de **clubs distincts** renseignés sur l'épreuve — dénominateur du
   *  « et N autres clubs ». Attention au faux ami : `categories_total` compte
   *  des **participants**, celui-ci compte des **clubs** (#486). */
  clubs_total: number;
  histogram: Histogram | null;
  /** Colonnes de temps intermédiaires du tableau — stables d'une page à l'autre. */
  split_keys: string[];
  /** Médiane des `split_gap_ratio` de l'épreuve — la **référence** à laquelle
   *  se juge l'écart d'une ligne. Un écart partagé par toutes les lignes est un
   *  segment que le chronométreur ne publie pas, pas une ligne fausse.
   *  `null` quand aucune ligne n'est évaluable (#486). */
  split_gap_median: number | null;
  /** Nombre de lignes évaluables — la médiane d'une population de neuf n'est pas
   *  une référence, et l'écran a besoin de le savoir pour se taire (#486). */
  split_gap_rows: number;
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
  /**
   * Groupes dont on est membre (#197) — « membre du Codir ». Rendu à tout
   * connecté, **sans exiger `groups:read`** : la question ne porte que sur soi.
   * Ne dit rien des droits, qui se lisent dans `permissions` seul.
   */
  groups: SessionGroup[];
}

/** Un groupe tel que son membre se le voit — sans membres ni pouvoirs (#197). */
export interface SessionGroup {
  id: number;
  slug: string;
  name: string;
  organisation_id: number;
}

/**
 * Ce qu'une suppression d'épreuve détruirait, chiffré **avant** le geste (#117).
 *
 * `athletes` n'est pas le nombre d'inscrits : c'est celui des coureurs dont
 * toutes les participations sont sur cette épreuve, donc ceux qui
 * disparaîtront avec elle. La confirmation annonce ce nombre-là, sans quoi
 * elle sous-déclarerait un geste sans retour en arrière.
 */
export interface CourseDeletionImpact {
  course_id: number;
  name: string;
  participations: number;
  athletes: number;
}

/**
 * Ce qu'une purge totale des résultats détruirait (#384).
 *
 * `athletes` est le compte total de fiches coureur : vider `participations`
 * entièrement laisse *toute* fiche orpheline — `Participation.athlete_id` est
 * la seule FK vers `Athlete` jamais peuplée — donc c'est le compte de la table
 * entière, pas seulement des coureurs inscrits quelque part.
 */
export interface ParticipationsWipeImpact {
  participations: number;
  athletes: number;
}

/**
 * Ce qu'une purge totale des épreuves détruirait (#384, suite).
 *
 * Contrairement à `ParticipationsWipeImpact`, ce geste emporte aussi les
 * épreuves elles-mêmes et leurs sources — `courses` s'ajoute donc aux deux
 * compteurs déjà connus.
 */
export interface CoursesWipeImpact {
  courses: number;
  participations: number;
  athletes: number;
}

/** Ce qu'une purge totale des résultats a détruit, une fois faite (#501). */
export interface ParticipationsWipeResult {
  participations_deleted: number;
  athletes_purged: number;
  courses_reset: number;
}

/** Ce qu'une purge totale des épreuves a détruit, une fois faite (#501). */
export interface CoursesWipeResult {
  courses_deleted: number;
  athletes_purged: number;
}

/** Une épreuve côté aperçu de fusion — miroir de `MergeImpactCourse` (#286). */
export interface MergeImpactCourse {
  id: number;
  name: string;
  event_date: string | null;
  event_type: string;
  is_relay: boolean;
  provider: string;
  participations: number;
}

/**
 * Ce qu'une fusion emporterait, chiffré **avant** le geste (#286).
 *
 * `participations_without_match` est le nombre de résultats de `absorbed` qui
 * n'ont pas d'équivalent chez `target` : ces athlètes disparaissent purement et
 * simplement de l'épreuve, la fusion ne re-scrape rien pour les récupérer.
 * `tcn_participations_without_match` isole ceux du club dans ce total — le
 * chiffre qui pèse le plus dans la décision d'un administrateur.
 */
export interface CourseMergeImpact {
  target: MergeImpactCourse;
  absorbed: MergeImpactCourse;
  participations_without_match: number;
  tcn_participations_without_match: number;
  athletes_orphaned: number;
  same_source_url: boolean;
}

/** Résultat d'une fusion (#287) — `sources` dans la forme de `GET /courses/{id}/sources`. */
export interface CourseMergeResult {
  target_id: number;
  absorbed_id: number;
  participations_deleted: number;
  athletes_purged: number;
  source_added: boolean;
  sources: CourseSource[];
}

/** Une épreuve candidate à un doublon — miroir de `DuplicateCourse` (#288). */
export interface DuplicateCourse {
  id: number;
  name: string;
  event_date: string | null;
  event_type: string;
  is_relay: boolean;
  provider: string;
  source_url: string;
  total: number;
  tcn_count: number;
}

/** Une paire suspecte, jamais un cluster — miroir de `DuplicateCandidate` (#288). */
export interface DuplicateCandidate {
  reason: "same_source_url" | "shared_event_id" | "close_names";
  reason_label: string;
  courses: DuplicateCourse[];
}

export interface DuplicateCandidateList {
  candidates: DuplicateCandidate[];
}

/** Ce que l'écran reçoit après avoir écarté une paire de doublons (#754). */
export interface DuplicateIgnoreResult {
  course_id_a: number;
  course_id_b: number;
  ignored_at: string;
}

/**
 * Une fiche coureur **complète**, servie derrière le pouvoir `athletes:read` (#117).
 *
 * Deux champs de plus que `AthleteBrief`, et ce sont les deux qui permettent de
 * départager deux homonymes avant un rattachement sans retour en arrière : la
 * date de naissance — seule donnée personnelle fermée du site — et le nombre de
 * résultats portés par la fiche.
 */
export interface AdminAthlete {
  id: number;
  nom: string;
  prenom: string;
  birth_date: string | null;
  gender: string;
  club: string | null;
  participations: number;
}

// Miroir de VolunteerActionSelfCreate/Out backend (#778) — formulaire public,
// seul chemin de création restant (#780).
export interface VolunteerActionSelfCreate {
  athlete_id: number;
  title: string;
  description: string;
}

export interface VolunteerActionSelfOut {
  id: number;
  athlete_id: number;
  season: number;
  title: string;
  description: string;
  status: string;
  declared_by_user_id: number | null;
  created_at: string;
}

// Miroir de AdminVolunteerActionOut backend (#779/#781/#817) — file d'admin
// et liste des actions validées d'un athlète. title/description optionnels :
// une ligne créée par le chemin admin existant (#709) ne les renseigne jamais.
export interface AdminVolunteerActionOut {
  id: number;
  athlete_id: number;
  athlete_nom: string;
  athlete_prenom: string;
  season: number;
  title: string | null;
  description: string | null;
  status: string;
  declared_by_user_id: number | null;
  created_at: string;
}

// Miroir de SeasonValidationOut backend (#709).
export interface SeasonValidation {
  athlete_id: number;
  season: number;
  validated_by_user_id: number;
  validated_at: string;
}

// Les trois signaux du barème de validation (#709, FR-012).
export interface SeasonQuota {
  validated_count: number;
  has_volunteer_action: boolean;
  season_validated: boolean;
}

/**
 * Corrections partielles (#117) — seuls les champs **présents** sont écrits.
 *
 * `event_date: null` est une mise à vide légitime et se distingue d'un champ
 * absent : c'est pourquoi ces types sont manipulés en `Partial<>`, jamais en
 * objets complets.
 */
export interface AdminCourseUpdate {
  name: string;
  event_date: string | null;
  event_type: string;
  is_relay: boolean;
}

export interface AdminAthleteUpdate {
  nom: string;
  prenom: string;
  birth_date: string | null;
  /** Club **actuel** : `null` retire le club, `""` est refusé par l'API (#439). */
  club: string | null;
}

/**
 * Un lancement de batch, vu de l'interface (#47).
 *
 * Les énumérations sont **en anglais**, comme le contrat : ce sont des valeurs
 * techniques, et le français d'affichage est produit par les composants. Les
 * traduire côté serveur figerait une traduction dans un contrat d'API.
 */
export interface BatchRun {
  id: number;
  label: string;
  state: "pending" | "running" | "completed";
  outcome: "success" | "failure" | "cancelled" | null;
  started_at: string;
  duration_s: number | null;
  triggered_by: "ui" | "schedule" | "manual";
  report_available: boolean;
  external_url: string;
}

/**
 * Le bilan — la charge `--json` de la CLI, telle quelle.
 *
 * Deux unités s'y côtoient, et l'affichage doit les nommer comme le fait le
 * rapport texte : `unique_supported`, `processed` et `errors` comptent des
 * **épreuves** ; `imported`, `updated` et `skipped` des **participants**.
 */
export interface BatchReport {
  unique_supported: number;
  processed: number;
  errors: number;
  imported: number;
  updated: number;
  skipped: number;
  rows_without_link?: number;
  ignored_by_host?: Record<string, number>;
  interrupted: boolean;
  failures: { url: string; label: string; message: string }[];
}

/** Les options d'une reprise filtrée. La base visée n'en fait pas partie. */
export interface RescrapeLaunch {
  mode: "rescrape";
  provider?: string;
  older_than?: number;
  limit?: number;
  dry_run?: boolean;
}

/** La réponse au lancement — sans identifiant d'exécution : le dispatch n'en rend aucun. */
export interface BatchLaunched {
  correlation_id: string;
  state: "pending";
  /** Renseignés au lancement depuis un fichier seulement. */
  epreuves?: number;
  ignored_by_host?: Record<string, number>;
}

/** Une colonne du fichier téléversé, telle que l'écran la présente. */
export interface ColumnPreview {
  index: number;
  header: string;
  /** Zéro sur une colonne d'hyperliens sans texte — c'est ce qui la rend visible. */
  link_count: number;
  samples: string[];
}

export interface SheetColumns {
  row_count: number;
  /** `null` quand aucune colonne ne porte de lien : l'écran le dit, il ne devine pas. */
  suggested_index: number | null;
  columns: ColumnPreview[];
}

/**
 * Composition des rôles (#115, écran #240).
 *
 * `code` est un identifiant technique **stable** — il traverse la base, un
 * renommage y laisserait des lignes inertes. `label` et `description` sont du
 * français d'affichage, écrits une seule fois, côté serveur
 * (`backend/app/core/permissions.py`) : les retraduire ici en ferait un second
 * lieu où le vocabulaire se décide.
 */
export interface Permission {
  code: string;
  label: string;
  description: string;
}

/**
 * Les pouvoirs d'une fonctionnalité, **dans l'ordre d'affichage du serveur**.
 *
 * Composer un rôle en cochant dans une liste plate de dix-huit codes techniques
 * est le geste qu'on veut éviter : ce regroupement est la feature. Ne pas le
 * ré-aplatir, ne pas le retrier.
 */
export interface PermissionGroup {
  feature: string;
  permissions: Permission[];
}

/**
 * Un rôle, sa composition et son nombre de porteurs.
 *
 * `stale_permissions` liste les codes présents en base mais absents de
 * l'inventaire — inertes, purgeables, jamais bloquants. Les séparer de
 * `permissions` est ce qui rend l'écran honnête : « ce rôle porte un code que
 * l'application ne connaît plus » se lit, « ce rôle porte 4 pouvoirs dont un
 * fantôme » ne se lit pas.
 */
export interface Role {
  id: number;
  organisation_id: number | null;
  slug: string;
  name: string;
  description: string;
  is_system: boolean;
  is_superuser: boolean;
  permissions: string[];
  stale_permissions: string[];
  holders: number;
}

/** Création d'un rôle. Le `slug` est fixé **une fois pour toutes**. */
export interface RoleCreate {
  slug: string;
  name: string;
  description?: string;
  permissions?: string[];
  is_superuser?: boolean;
}

/**
 * Modification d'un rôle. Tout est facultatif, et `permissions` **remplace**
 * l'ensemble — l'envoyer sans que la composition ait changé purgerait les codes
 * périmés en silence.
 *
 * **Ni `slug`, ni `is_system`, ni `holders`** : le schéma serveur est
 * `extra="forbid"`, un champ de trop rend 422 plutôt que d'être ignoré. Le type
 * l'interdit donc à la compilation, où l'erreur coûte le moins cher.
 */
export interface RoleUpdate {
  name?: string;
  description?: string;
  permissions?: string[];
  is_superuser?: boolean;
}

/**
 * Bilan d'une révocation d'urgence (#169).
 *
 * Deux unités, et chaque nom le dit : `sessions` compte des jetons coupés,
 * `accounts` les comptes qui en portaient au moins un — jamais tous ceux de la
 * base, sans quoi un geste dans le vide aurait l'air d'un geste utile.
 */
export interface SessionRevocation {
  sessions: number;
  accounts: number;
}

/** Corps de `POST /feedback` (#267) — route publique. */
export interface FeedbackCreate {
  type: "bug" | "feedback";
  title: string;
  body: string;
  page_url?: string | null;
  user_agent?: string | null;
  /** Champ caché du formulaire : jamais rempli par un visiteur humain. */
  honeypot?: string | null;
}

/** Réponse minimale de `POST /feedback` — identique en cas de honeypot. */
export interface FeedbackCreated {
  id: number;
  status: string;
}

/** Un retour utilisateur, tel que rendu à un pouvoir `feedback:read`. */
export interface Feedback {
  id: number;
  type: "bug" | "feedback";
  title: string;
  body: string;
  page_url: string | null;
  user_agent: string | null;
  status: "nouveau" | "en_cours" | "traite" | "ignore";
  github_url: string | null;
  created_at: string;
  email: string | null;
}

/**
 * `GET /admin/feedback/counts` — le nombre de signalements par statut (#500).
 * Les quatre statuts sont toujours présents, à zéro le cas échéant : la barre
 * de filtres affiche ses quatre entrées même sur une base vide.
 */
export interface FeedbackCounts {
  nouveau: number;
  en_cours: number;
  traite: number;
  ignore: number;
  total: number;
}

/** Corps de `PATCH /admin/feedback/{id}` — champs modifiés seulement. */
export interface FeedbackUpdate {
  status?: Feedback["status"];
  github_url?: string;
}

/** Une entrée du journal d'administration (#501). */
export interface AdminActionLogEntry {
  id: number;
  created_at: string;
  user_name: string;
  action: string;
  entity_type: string;
  entity_id: number;
  payload: Record<string, unknown> | null;
}

/** Une page du journal — `total` porte le compte plein, pas celui de la page. */
export interface AdminActionLogPage {
  entries: AdminActionLogEntry[];
  total: number;
}

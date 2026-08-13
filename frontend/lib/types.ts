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

interface EventOut {
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

interface CategoryCount {
  name: string;
  count: number;
}

interface ClubCount {
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

/** Corps de `POST /admin/feedback` (#267) — route publique. */
export interface FeedbackCreate {
  type: "bug" | "feedback";
  title: string;
  body: string;
  page_url?: string | null;
  user_agent?: string | null;
  /** Champ caché du formulaire : jamais rempli par un visiteur humain. */
  honeypot?: string | null;
}

/** Réponse minimale de `POST /admin/feedback` — identique en cas de honeypot. */
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

/** Corps de `PATCH /admin/feedback/{id}` — champs modifiés seulement. */
export interface FeedbackUpdate {
  status?: Feedback["status"];
  github_url?: string;
}

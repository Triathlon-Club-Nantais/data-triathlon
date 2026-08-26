import { cookies } from "next/headers";
import { ApiError } from "@/lib/api/client";
import { errorDetail, toQuery } from "@/lib/api/query";
import { NAV_WIDTH_COOKIE } from "@/lib/nav-cookies";
import type {
  AthleteDetail,
  AthleteSeasonActivity,
  AuthMethod,
  CourseDetail,
  CourseQuery,
  CourseSource,
  CourseSummary,
  EventPage,
  Participation,
  ParticipationFilters,
  Season,
  SessionUser,
  Stats,
} from "@/lib/types";

const API_URL = process.env.API_URL || "http://localhost:8001";
const BASE = `${API_URL}/api/v1`;

/** Fenêtre de revalidation optionnelle (#352) — `undefined` garde `no-store`. */
export type FetchOpts = { revalidateSeconds?: number };

/**
 * Fenêtre courte pour `/dashboard` et `/club` (#352) — les deux pages dont le
 * coût mesuré (sondage du 2026-08-14) justifie un `revalidate`, une fois
 * #350/#351 corrigés. `/ajouter` (#376) partage la même fenêtre pour une
 * raison différente : ce n'est pas son coût par appel qui pose problème, mais
 * son prefetch continu par le bouton « + » de `AppNav`, présent sur toutes
 * les pages. Dans les trois cas, les imports tournent par batch de plusieurs
 * dizaines de minutes (`docs/ci-cd.md`), jamais en temps réel : 30 s masque
 * le coût de chargement (ou le prefetch répété) pour l'écrasante majorité des
 * visites sans retarder la visibilité d'un import terminé au-delà de ce qu'un
 * visiteur tolère.
 */
export const SHORT_REVALIDATE_SECONDS = 30;

/**
 * Construit l'en-tête `cookie` relayé au backend, **hors** `NAV_WIDTH_COOKIE`
 * (#482, NAV-3) : purement une préférence d'affichage côté client, jamais lue
 * par l'API, mais qui ferait sinon partie de la clé du Data Cache (#526) —
 * exactement la fenêtre de partage inter-visiteurs que #352 cherche à
 * préserver le plus possible.
 *
 * Réservée à `serverFetchAuthed`/`serverFetchAuthedRaw` (#586) : ces deux
 * variantes lisent des cookies que `serverFetch` n'a jamais besoin de
 * connaître (`tcn_session`, la session SSO), donc une exclusion reste le bon
 * outil. `serverFetch`, lui, prend un allowlist — voir `siteAccessCookieHeader`.
 */
function cookieHeader(jar: Awaited<ReturnType<typeof cookies>>): string {
  return jar
    .getAll()
    .filter((c) => c.name !== NAV_WIDTH_COOKIE)
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
}

/**
 * Nom du cookie de session d'accès au site (#509) — miroir de
 * `site_access.SITE_SESSION_COOKIE` côté backend (`backend/app/services/site_access.py`).
 * Jamais préfixé `__Host-`, à la différence du cookie de session SSO
 * (`app/api/v1/auth.py`) : `site_access.py` le pose tel quel.
 */
const SITE_SESSION_COOKIE = "tcn_site_session";

/**
 * En-tête `cookie` **minimal** relayé par `serverFetch` (#586) : seul
 * `SITE_SESSION_COOKIE` conditionne l'accès aux routes qu'elle sert
 * (`require_site_access`, backend — `athletes`, `courses`, `participations`,
 * `stats`) ; aucune ne lit `tcn_session` (SSO), `tcn_benevole_session`, un
 * cookie PostHog ni `NAV_WIDTH_COOKIE`. Un allowlist plutôt que l'exclusion de
 * `cookieHeader` : la liste de ce qu'une route *ignore* grandit à chaque
 * cookie ajouté au front (SSO, consentement, analytics…), celle de ce dont
 * elle a *besoin* ne bouge que si le backend change de garde.
 *
 * Relayer le jar entier (comme avant #586) faisait varier la clé du Data
 * Cache sur des cookies dont ces routes n'ont rien à faire — jusqu'à casser,
 * pour un même visiteur qui recharge sa propre page dans les 30 s, le partage
 * *intra-visiteur* que #526 avait laissé intact : un cookie PostHog qui
 * tourne ou un `tcn_auth_state` posé puis retiré par une tentative de
 * connexion SSO suffisait à changer la clé.
 *
 * Ne restaure **pas** le partage *inter-visiteurs* de #352 : `sign_cookie`
 * (`backend/app/services/shared_password.py`) inclut l'horodatage de son
 * émission dans la valeur du cookie, qui reste donc unique par visiteur quel
 * que soit le filtrage ici. Le résoudre demande de découpler la garde de la
 * clé de cache côté backend — une frontière de sécurité qu'#586 documente
 * mais ne tranche pas, faute de mesure du taux de succès réel du Data Cache en
 * production.
 */
function siteAccessCookieHeader(jar: Awaited<ReturnType<typeof cookies>>): string {
  const cookie = jar.get(SITE_SESSION_COOKIE);
  return cookie ? `${SITE_SESSION_COOKIE}=${cookie.value}` : "";
}

/**
 * Relaie le cookie d'accès au site, **y compris pour les routes publiques**
 * (#526).
 *
 * Cookie-libre jusqu'à #526, au nom du prérendu statique des six pages
 * publiques en rendu serveur. #509 a rendu la justification caduque (le layout
 * de `app/(public_restricted)/` lit déjà le cookie du mot de passe site
 * au-dessus d'elles, donc elles sont dynamiques de toute façon) **et** le
 * relais obligatoire : `require_site_access` garde `athletes`, `courses`,
 * `participations` et `stats`, et il est fail-closed. Sans cookie, chacune de
 * ces pages levait une `ApiError` 401 en pleine passe de rendu serveur, soit
 * l'écran d'erreur (React #441) sur tout le site dès qu'un mot de passe site
 * était configuré.
 */
async function serverFetch<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const jar = await cookies();
  const res = await fetch(`${BASE}${path}`, {
    ...(opts.revalidateSeconds !== undefined
      ? { next: { revalidate: opts.revalidateSeconds } }
      : { cache: "no-store" }),
    headers: { cookie: siteAccessCookieHeader(jar) },
  });
  if (!res.ok) {
    // `ApiError` plutôt qu'un `Error` nu : sans le statut, un appelant ne peut
    // pas distinguer une ressource absente d'un backend en panne, et finit par
    // afficher « introuvable » sur les deux.
    throw new ApiError(res.status, await errorDetail(res));
  }
  return res.json() as Promise<T>;
}

/**
 * Variante **authentifiée** de `serverFetch`.
 *
 * Les deux relaient les cookies depuis #526 : ce qui les sépare est la lecture
 * du 401, plus le cookie. Rend `null` sur 401 — anonyme est un état normal,
 * pas une panne.
 *
 * Toute autre réponse non-OK lève une `ApiError`, comme `serverFetch` : un
 * `Error` nu jetterait le statut, et l'appelant ne pourrait plus distinguer un
 * backend injoignable (502, démarrage à froid) d'une de nos routes qui plante
 * (500). La garde `/admin` lit précisément cette différence.
 */
async function serverFetchAuthed<T>(path: string): Promise<T | null> {
  const jar = await cookies();
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: { cookie: cookieHeader(jar) },
  });
  if (res.status === 401) return null;
  if (!res.ok) {
    throw new ApiError(res.status, await errorDetail(res));
  }
  return res.json() as Promise<T>;
}

/**
 * Variante de `serverFetchAuthed` qui ne rend qu'un booléen.
 *
 * `checkSiteAccess` n'a besoin que de savoir si le cookie est valide — mais
 * `false` doit rester réservé au seul 401 **avéré** (cookie absent, invalide
 * ou expiré). Un réseau en échec ou un statut ≠ 200/401 (démarrage à froid,
 * 5xx) ne dit rien sur la validité du cookie : les confondre avec `false`
 * ferait rediriger vers `/acces` pendant une panne backend, exactement ce que
 * `admin/layout.tsx` évite déjà pour sa propre garde via son couple
 * `panne()`/`INDISPONIBLE`. On lève donc une `ApiError` (ou on laisse
 * remonter l'échec réseau) sur tout ce qui n'est ni 200 ni 401, à charge pour
 * l'appelant — `app/(public_restricted)/layout.tsx` — de les traiter comme lui.
 */
async function serverFetchAuthedRaw(path: string): Promise<boolean> {
  const jar = await cookies();
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: { cookie: cookieHeader(jar) },
  });
  if (res.status === 401) return false;
  if (!res.ok) {
    throw new ApiError(res.status, await errorDetail(res));
  }
  return true;
}

export const apiServer = {
  listParticipations: (filters: ParticipationFilters = {}, fetchOpts: FetchOpts = {}) =>
    serverFetch<Participation[]>(
      `/participations${toQuery(filters as Record<string, unknown>)}`,
      fetchOpts,
    ),
  getAthlete: (id: number) => serverFetch<AthleteDetail>(`/athletes/${id}`),
  listAthleteSeasonActivity: (
    opts: { scope?: string; seasons?: number[]; federal_only?: boolean } = {},
  ) =>
    serverFetch<AthleteSeasonActivity[]>(
      `/athletes/season-activity${toQuery(opts as Record<string, unknown>)}`,
    ),
  /**
   * Détail d'une participation — seule route à peupler `stats`.
   *
   * Le calcul parcourt tout le classement de la course : on le paie pour une
   * participation consultée, jamais par ligne d'un tableau de finishers.
   */
  getParticipation: (id: number) => serverFetch<Participation>(`/participations/${id}`),
  getCourse: (id: number, opts: CourseQuery = {}) =>
    serverFetch<CourseDetail>(`/courses/${id}${toQuery(opts as Record<string, unknown>)}`),
  /**
   * Synthèse d'épreuve entière : appel **séparé** du classement, et sans
   * paramètre. C'est ce qui garantit que la recherche en cours ne la modifie
   * pas (#163).
   */
  getCourseSummary: (id: number) => serverFetch<CourseSummary>(`/courses/${id}/summary`),
  /** Sources connues de l'épreuve, active en tête (#284) — lecture publique (D4). */
  getCourseSources: (id: number) => serverFetch<CourseSource[]>(`/courses/${id}/sources`),
  listEvents: (filters: ParticipationFilters = {}, fetchOpts: FetchOpts = {}) =>
    serverFetch<EventPage>(
      `/courses/events${toQuery(filters as Record<string, unknown>)}`,
      fetchOpts,
    ),
  getStats: (
    opts: { scope?: string; seasons?: number[]; federal_only?: boolean } = {},
    fetchOpts: FetchOpts = {},
  ) => serverFetch<Stats>(`/stats${toQuery(opts)}`, fetchOpts),
  listSeasons: (opts: { scope?: string; federal_only?: boolean } = {}, fetchOpts: FetchOpts = {}) =>
    serverFetch<Season[]>(`/stats/seasons${toQuery(opts)}`, fetchOpts),
  /** Session du visiteur, ou `null` s'il est anonyme (#114). */
  getSession: () => serverFetchAuthed<SessionUser>("/auth/me"),
  /**
   * Moyens de connexion disponibles, côté serveur.
   *
   * Publique, et exemptée de `require_site_access` : elle **répond** sans
   * session, ce qui permet à la garde `/admin` de distinguer « pas connecté »
   * (liste non vide → rediriger) de « aucune connexion possible » (liste vide →
   * laisser passer, FR-036). Le cookie que `serverFetch` relaie (#526, réduit
   * au seul cookie d'accès au site par #586) n'y change rien : ce qui compte
   * est qu'elle n'en exige aucun, pas qu'on s'abstienne de l'envoyer.
   */
  listAuthMethods: () => serverFetch<AuthMethod[]>("/auth/methods"),
  /** Session du mot de passe site (#509) — vrai si le cookie est valide. */
  checkSiteAccess: () => serverFetchAuthedRaw("/site-access/session"),
};

import { cookies } from "next/headers";
import { ApiError } from "@/lib/api/client";
import { errorDetail, toQuery } from "@/lib/api/query";
import type {
  AthleteDetail,
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
 * Fenêtre courte pour `/dashboard` et `/club` (#352) — les deux seules pages
 * dont le coût mesuré (sondage du 2026-08-14) justifie un `revalidate`, une
 * fois #350/#351 corrigés. Les imports tournent par batch de plusieurs
 * dizaines de minutes (`docs/ci-cd.md`), jamais en temps réel : 30 s masque
 * le coût de chargement pour l'écrasante majorité des visites sans retarder
 * la visibilité d'un import terminé au-delà de ce qu'un visiteur tolère.
 */
export const SHORT_REVALIDATE_SECONDS = 30;

async function serverFetch<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const res = await fetch(
    `${BASE}${path}`,
    opts.revalidateSeconds !== undefined
      ? { next: { revalidate: opts.revalidateSeconds } }
      : { cache: "no-store" },
  );
  if (!res.ok) {
    // `ApiError` plutôt qu'un `Error` nu : sans le statut, un appelant ne peut
    // pas distinguer une ressource absente d'un backend en panne, et finit par
    // afficher « introuvable » sur les deux.
    throw new ApiError(res.status, await errorDetail(res));
  }
  return res.json() as Promise<T>;
}

/**
 * Variante **authentifiée** de `serverFetch`, qui relaie les cookies entrants.
 *
 * Fonction séparée, et `serverFetch` volontairement **inchangé** : six pages
 * publiques en rendu serveur l'utilisent, et lire les cookies les rendrait
 * toutes dynamiques — on paierait le prérendu statique du site public pour
 * afficher un avatar.
 *
 * Rend `null` sur 401 : anonyme est un état normal, pas une panne.
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
    headers: { cookie: jar.toString() },
  });
  if (res.status === 401) return null;
  if (!res.ok) {
    throw new ApiError(res.status, await errorDetail(res));
  }
  return res.json() as Promise<T>;
}

export const apiServer = {
  listParticipations: (filters: ParticipationFilters = {}, fetchOpts: FetchOpts = {}) =>
    serverFetch<Participation[]>(
      `/participations${toQuery(filters as Record<string, unknown>)}`,
      fetchOpts,
    ),
  getAthlete: (id: number) => serverFetch<AthleteDetail>(`/athletes/${id}`),
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
   * Public : passe par `serverFetch`, sans cookie. C'est ce qui permet à la
   * garde `/admin` de distinguer « pas connecté » (liste non vide → rediriger)
   * de « aucune connexion possible » (liste vide → laisser passer, FR-036).
   */
  listAuthMethods: () => serverFetch<AuthMethod[]>("/auth/methods"),
};

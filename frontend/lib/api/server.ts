import { cookies } from "next/headers";
import type {
  AthleteDetail,
  AuthMethod,
  CourseDetail,
  EventPage,
  Participation,
  ParticipationFilters,
  PendingProvider,
  Season,
  SessionUser,
  Stats,
} from "@/lib/types";

const API_URL = process.env.API_URL || "http://localhost:8001";
const BASE = `${API_URL}/api/v1`;

async function serverFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Erreur API (${res.status})`);
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
 */
async function serverFetchAuthed<T>(path: string): Promise<T | null> {
  const jar = await cookies();
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    headers: { cookie: jar.toString() },
  });
  if (res.status === 401) return null;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Erreur API (${res.status})`);
  }
  return res.json() as Promise<T>;
}

function toQuery(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    if (Array.isArray(v)) {
      if (v.length > 0) params.set(k, v.join(","));
      return;
    }
    params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const apiServer = {
  listParticipations: (filters: ParticipationFilters = {}) =>
    serverFetch<Participation[]>(`/participations${toQuery(filters as Record<string, unknown>)}`),
  getAthlete: (id: number) => serverFetch<AthleteDetail>(`/athletes/${id}`),
  getCourse: (id: number) => serverFetch<CourseDetail>(`/courses/${id}`),
  listEvents: (filters: ParticipationFilters = {}) =>
    serverFetch<EventPage>(`/courses/events${toQuery(filters as Record<string, unknown>)}`),
  getStats: (opts: { scope?: string; seasons?: number[]; federal_only?: boolean } = {}) =>
    serverFetch<Stats>(`/stats${toQuery(opts)}`),
  listSeasons: (opts: { scope?: string; federal_only?: boolean } = {}) =>
    serverFetch<Season[]>(`/stats/seasons${toQuery(opts)}`),
  listPendingProviders: () =>
    serverFetch<PendingProvider[]>("/admin/pending-providers"),

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

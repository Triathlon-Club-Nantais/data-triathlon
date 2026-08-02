import type {
  AthleteDetail,
  AuthMethod,
  CourseDetail,
  EventPage,
  GeoEvent,
  ImportResult,
  Participation,
  ParticipationFilters,
  PendingProvider,
  ScrapedPreview,
  Season,
  SessionUser,
  Stats,
} from "@/lib/types";

const BASE = "/api/v1";

/**
 * Erreur d'API porteuse de son statut HTTP.
 *
 * Sans lui, un 401 était indiscernable d'un 500 : les deux arrivaient en `Error`
 * nu. La session en dépend — « pas connecté » est un état normal de la page, pas
 * une panne à signaler. Reste une `Error`, donc rien de l'existant ne change.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, err.detail || "Erreur réseau");
  }
  if (res.status === 204) return null as T;
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

export const apiClient = {
  // `supported` vient du registre backend : le front ne tient aucune liste de
  // providers (la sienne avait divergé, cf. ProviderDetector).
  detectProvider: (url: string) =>
    request<{ provider: string; supported?: boolean }>(
      `/scrape/detect${toQuery({ url })}`,
    ),

  importEvent: (url: string) =>
    request<ImportResult>("/scrape/event", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  saveParticipation: (data: Partial<ScrapedPreview>) =>
    request<Participation>("/participations", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listParticipations: (filters: ParticipationFilters = {}) =>
    request<Participation[]>(`/participations${toQuery(filters as Record<string, unknown>)}`),

  deleteParticipation: (id: number) =>
    request<null>(`/participations/${id}`, { method: "DELETE" }),

  getAthlete: (id: number) => request<AthleteDetail>(`/athletes/${id}`),
  getCourse: (id: number) => request<CourseDetail>(`/courses/${id}`),

  listEvents: (filters: ParticipationFilters = {}) =>
    request<EventPage>(`/courses/events${toQuery(filters as Record<string, unknown>)}`),

  getStats: (opts: { scope?: string; seasons?: number[]; federal_only?: boolean } = {}) =>
    request<Stats>(`/stats${toQuery(opts)}`),

  // Version courante du backend — sert au footer du layout (#134) qui compare
  // avec `process.env.NEXT_PUBLIC_APP_VERSION` pour détecter les mismatches.
  getVersion: () => request<{ version: string }>("/version"),

  listSeasons: (opts: { scope?: string; federal_only?: boolean } = {}) =>
    request<Season[]>(`/stats/seasons${toQuery(opts)}`),
  getEventsGeo: (opts: { scope?: string; federal_only?: boolean } = {}) =>
    request<GeoEvent[]>(`/stats/events-geo${toQuery(opts)}`),

  // ── Authentification (#114) ────────────────────────────────────────────────
  // Aucune méthode de connexion n'est codée en dur ici : l'écran de connexion
  // se construit à partir de ce que le backend déclare (FR-031).
  listAuthMethods: () => request<AuthMethod[]>("/auth/methods"),
  getSession: () => request<SessionUser>("/auth/me"),
  logout: () => request<null>("/auth/logout", { method: "POST" }),

  listPendingProviders: () =>
    request<PendingProvider[]>("/admin/pending-providers"),
  reportPendingProvider: (url: string) =>
    request<PendingProvider>("/admin/pending-providers", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  markProviderHandled: (id: number) =>
    request<null>(`/admin/pending-providers/${id}`, { method: "DELETE" }),
};

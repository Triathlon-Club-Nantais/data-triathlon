import type {
  AthleteDetail,
  CourseDetail,
  EventOut,
  GeoEvent,
  ImportResult,
  Participation,
  ParticipationFilters,
  PendingProvider,
  ScrapedPreview,
  Stats,
} from "@/lib/types";

const BASE = "/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Erreur réseau");
  }
  if (res.status === 204) return null as T;
  return res.json() as Promise<T>;
}

function toQuery(filters: Record<string, unknown>): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const apiClient = {
  detectProvider: (url: string) =>
    request<{ provider: string }>(`/scrape/detect${toQuery({ url })}`),

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
    request<EventOut[]>(`/courses/events${toQuery(filters as Record<string, unknown>)}`),

  getStats: (club?: string) => request<Stats>(`/stats${toQuery({ club })}`),
  getEventsGeo: (club?: string) =>
    request<GeoEvent[]>(`/stats/events-geo${toQuery({ club })}`),

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

import type {
  AthleteDetail,
  CourseDetail,
  EventPage,
  Participation,
  ParticipationFilters,
  PendingProvider,
  Season,
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
  getStats: (club?: string, seasons?: number[]) =>
    serverFetch<Stats>(`/stats${toQuery({ club, seasons })}`),
  listSeasons: (club?: string) =>
    serverFetch<Season[]>(`/stats/seasons${toQuery({ club })}`),
  listPendingProviders: () =>
    serverFetch<PendingProvider[]>("/admin/pending-providers"),
};

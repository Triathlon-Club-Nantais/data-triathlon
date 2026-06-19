import type { ParticipationFilters } from "@/lib/types";

export const queryKeys = {
  participations: (filters: ParticipationFilters = {}) =>
    ["participations", filters] as const,
  events: (filters: ParticipationFilters = {}) => ["events", filters] as const,
  courseParticipations: (courseId: number, club?: string, name?: string) =>
    ["course-participations", courseId, club ?? null, name ?? null] as const,
  stats: (club?: string) => ["stats", club ?? null] as const,
  pendingProviders: () => ["pending-providers"] as const,
};

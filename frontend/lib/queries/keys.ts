import type { ParticipationFilters } from "@/lib/types";

export const queryKeys = {
  participations: (filters: ParticipationFilters = {}) =>
    ["participations", filters] as const,
  events: (filters: ParticipationFilters = {}) => ["events", filters] as const,
  courseParticipations: (courseId: number, scope?: string, name?: string) =>
    ["course-participations", courseId, scope ?? null, name ?? null] as const,
  stats: (scope?: string) => ["stats", scope ?? null] as const,
  pendingProviders: () => ["pending-providers"] as const,
  allowedEmails: () => ["allowed-emails"] as const,
  session: () => ["session"] as const,
  authMethods: () => ["auth-methods"] as const,
};

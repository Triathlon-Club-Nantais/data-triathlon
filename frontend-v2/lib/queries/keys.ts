import type { ParticipationFilters } from "@/lib/types";

export const queryKeys = {
  participations: (filters: ParticipationFilters = {}) =>
    ["participations", filters] as const,
  stats: (club?: string) => ["stats", club ?? null] as const,
  pendingProviders: () => ["pending-providers"] as const,
};

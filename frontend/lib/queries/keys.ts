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
  adminCourses: (page = 1) => ["admin-courses", page] as const,
  adminAthletes: (search: string) => ["admin-athletes", search] as const,
  adminAthlete: (id: number) => ["admin-athlete", id] as const,
  // Clé distincte de `courseParticipations` : celle-ci stocke un `CourseDetail`,
  // l'autre un `Participation[]`. Même clé, deux formes = un écran qui plante.
  adminCourseDetail: (courseId: number, q: string) =>
    ["admin-course-detail", courseId, q] as const,
  courseDeletionImpact: (courseId: number) =>
    ["course-deletion-impact", courseId] as const,
  session: () => ["session"] as const,
  authMethods: () => ["auth-methods"] as const,
};

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
  adminCourses: (page = 1, filtres: Record<string, string> = {}) =>
    ["admin-courses", page, filtres] as const,
  // Sous le même préfixe que la liste, délibérément : `CACHES_ADMIN.courses`
  // invalide « admin-courses », et un total resté sur l'ancien compte après une
  // suppression annoncerait une page 7 qui n'existe plus.
  adminCoursesCount: (filtres: Record<string, string> = {}) =>
    ["admin-courses", "count", filtres] as const,
  adminAthletes: (search: string) => ["admin-athletes", search] as const,
  adminAthlete: (id: number) => ["admin-athlete", id] as const,
  // Clé distincte de `courseParticipations` : celle-ci stocke un `CourseDetail`,
  // l'autre un `Participation[]`. Même clé, deux formes = un écran qui plante.
  adminCourseDetail: (courseId: number, q: string) =>
    ["admin-course-detail", courseId, q] as const,
  courseDeletionImpact: (courseId: number) =>
    ["course-deletion-impact", courseId] as const,
  adminUsers: () => ["admin-users"] as const,
  // Une seule clé pour `GET /admin/roles`, partagée par l'attribution (#239) et
  // la composition (#240) : deux clés donneraient deux caches de la même liste,
  // dont l'un afficherait un `holders` ou un nom que l'autre vient de changer.
  roles: () => ["roles"] as const,
  // L'inventaire des pouvoirs est servi depuis le code Python : il ne change
  // qu'au déploiement, d'où le `staleTime: Infinity` de son hook.
  adminPermissions: () => ["admin-permissions"] as const,
  session: () => ["session"] as const,
  authMethods: () => ["auth-methods"] as const,
};

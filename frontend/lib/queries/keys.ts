import type { ParticipationFilters } from "@/lib/types";

export const queryKeys = {
  events: (filters: ParticipationFilters = {}) => ["events", filters] as const,
  pendingProviders: () => ["pending-providers"] as const,
  // Sous le même préfixe que la liste, à dessein : voir `adminCoursesCount`.
  pendingProvidersCount: () => ["pending-providers", "count"] as const,
  allowedEmails: () => ["allowed-emails"] as const,
  benevoleAccessConfig: () => ["benevole-access-config"] as const,
  siteAccessConfig: () => ["site-access-config"] as const,
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
  participationsWipeImpact: () => ["participations-wipe-impact"] as const,
  coursesWipeImpact: () => ["courses-wipe-impact"] as const,
  courseDuplicates: () => ["course-duplicates"] as const,
  // Sous le même préfixe que la liste, à dessein : voir `adminCoursesCount`.
  courseDuplicatesCount: () => ["course-duplicates", "count"] as const,
  courseMergeImpact: (courseId: number, absorbedId: number) =>
    ["course-merge-impact", courseId, absorbedId] as const,
  adminUsers: () => ["admin-users"] as const,
  // Une seule clé pour `GET /admin/roles`, partagée par l'attribution (#239) et
  // la composition (#240) : deux clés donneraient deux caches de la même liste,
  // dont l'un afficherait un `holders` ou un nom que l'autre vient de changer.
  roles: () => ["roles"] as const,
  groups: () => ["admin-groups"] as const,
  // Clé distincte de la liste : celle-ci stocke un `GroupDetail`, l'autre un
  // `Group[]`. Une écriture sur la composition périme **les deux** — le nombre
  // de membres vit sur la liste.
  group: (id: number) => ["admin-group", id] as const,
  // L'inventaire des pouvoirs est servi depuis le code Python : il ne change
  // qu'au déploiement, d'où le `staleTime: Infinity` de son hook.
  adminPermissions: () => ["admin-permissions"] as const,
  session: () => ["session"] as const,
  authMethods: () => ["auth-methods"] as const,
  providers: () => ["providers"] as const,
  batchRuns: () => ["batch-runs"] as const,
  batchReport: (runId: number) => ["batch-report", runId] as const,
  feedbackList: (sort: string, order: string, status: string) =>
    ["admin-feedback", sort, order, status] as const,
  // Sous le **même** préfixe que la liste, à dessein : changer un statut change
  // les deux, et `invalidateQueries({ queryKey: ["admin-feedback"] })` les
  // emporte alors d'un seul geste (#500).
  feedbackCounts: () => ["admin-feedback", "counts"] as const,
  // Clé distincte de la liste : celle-ci stocke un `Feedback` unique, l'autre
  // un tableau. Même patron que `group`/`groups`.
  feedback: (id: number) => ["admin-feedback-detail", id] as const,
  counterScope: () => ["counter-scope"] as const,
  clubAliases: () => ["club-aliases"] as const,
  adminActionLog: (page: number) => ["admin-action-log", page] as const,
  // Chargé à la demande, seulement quand l'athlète retenu est hors de
  // l'aperçu de 12 du roster club (#504, #641) — `RosterApercu`, seul
  // appelant. `federalOnly` fait partie de la clé : c'est un filtre distinct
  // du roster affiché, un rang calculé sur l'autre base afficherait un nombre
  // incohérent avec la liste sous les yeux.
  clubRosterRank: (athleteId: number, federalOnly: boolean) =>
    ["club-roster-rank", athleteId, federalOnly] as const,
  myVolunteerDeclarations: () => ["my-volunteer-declarations"] as const,
  adminVolunteerDeclarations: () => ["admin-volunteer-declarations"] as const,
};

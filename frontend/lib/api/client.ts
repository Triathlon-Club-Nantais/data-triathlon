import type {
  AdminAthlete,
  AdminAthleteUpdate,
  AdminCourseUpdate,
  AdminUser,
  AthleteDetail,
  AuthMethod,
  CourseBrief,
  CourseDeletionImpact,
  CourseDetail,
  CourseQuery,
  CourseSummary,
  EventPage,
  GeoEvent,
  ImportResult,
  Participation,
  ParticipationFilters,
  AllowedEmail,
  PendingProvider,
  Role,
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

/**
 * Le `detail` d'une réponse d'erreur, ramené à une chaîne affichable.
 *
 * Les `DomainError` du backend rendent `{"detail": "<français>"}` et se
 * réaffichent verbatim. Mais la validation Pydantic, elle, rend une **liste**
 * d'objets `{loc, msg, …}` : passée telle quelle à `new Error(message)`, elle
 * s'affichait « [object Object] » dans un toast. Le cas est atteignable sur
 * toute route à contrainte de champ ou `extra="forbid"`.
 */
function messageDErreur(detail: unknown, repli: string): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) =>
        typeof item === "object" && item !== null && "msg" in item
          ? String((item as { msg: unknown }).msg)
          : null,
      )
      .filter(Boolean);
    if (messages.length) return messages.join(" · ");
  }
  return repli || "Erreur réseau";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, messageDErreur(err.detail, res.statusText));
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
    request<{ provider: string; supported: boolean }>(
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
  getCourse: (id: number, opts: CourseQuery = {}) =>
    request<CourseDetail>(`/courses/${id}${toQuery(opts as Record<string, unknown>)}`),
  getCourseSummary: (id: number) => request<CourseSummary>(`/courses/${id}/summary`),

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

  // ── Administration des données (#117) ──────────────────────────────────────
  // Six ressources, six pouvoirs distincts côté serveur : l'écran ne fait que
  // cacher ce qu'il ne peut pas faire, il n'autorise rien.
  listCourses: (
    opts: {
      name?: string;
      event_type?: string;
      date_from?: string;
      date_to?: string;
      page?: number;
      page_size?: number;
    } = {},
  ) => request<CourseBrief[]>(`/courses${toQuery(opts)}`),
  countCourses: (
    opts: { name?: string; event_type?: string; date_from?: string; date_to?: string } = {},
  ) => request<{ total: number }>(`/courses/count${toQuery(opts)}`),
  getCourseDeletionImpact: (id: number) =>
    request<CourseDeletionImpact>(`/admin/courses/${id}/deletion-impact`),
  deleteCourse: (id: number) =>
    request<null>(`/admin/courses/${id}`, { method: "DELETE" }),
  updateCourse: (id: number, champs: Partial<AdminCourseUpdate>) =>
    request<CourseBrief>(`/admin/courses/${id}`, {
      method: "PATCH",
      body: JSON.stringify(champs),
    }),
  updateAthlete: (id: number, champs: Partial<AdminAthleteUpdate>) =>
    request<AdminAthlete>(`/admin/athletes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(champs),
    }),
  getAthleteAdmin: (id: number) => request<AdminAthlete>(`/admin/athletes/${id}`),
  searchAthletesAdmin: (search: string) =>
    request<AdminAthlete[]>(`/admin/athletes${toQuery({ search })}`),
  reassignParticipation: (participationId: number, athleteId: number) =>
    request<Participation>(`/admin/participations/${participationId}/reassign`, {
      method: "POST",
      body: JSON.stringify({ athlete_id: athleteId }),
    }),

  listPendingProviders: () =>
    request<PendingProvider[]>("/admin/pending-providers"),
  reportPendingProvider: (url: string) =>
    request<PendingProvider>("/admin/pending-providers", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  markProviderHandled: (id: number) =>
    request<null>(`/admin/pending-providers/${id}`, { method: "DELETE" }),

  // ── Accès au back-office (#170) ────────────────────────────────────────────
  // Les trois gestes exigent le pouvoir `allowed_emails:manage` ; un anonyme
  // obtient 401 et jamais la liste.
  listAllowedEmails: () => request<AllowedEmail[]>("/admin/allowed-emails"),
  // `roleId` omis (`undefined`) ≠ `null` : le premier laisse le rôle posé
  // intact, le second le **lève**. Le backend ne les distingue que par la
  // présence de la clé, et le second exige `roles:assign`.
  addAllowedEmail: (email: string, roleId?: number | null) =>
    request<AllowedEmail>("/admin/allowed-emails", {
      method: "POST",
      body: JSON.stringify(
        roleId === undefined ? { email } : { email, role_id: roleId },
      ),
    }),
  removeAllowedEmail: (id: number) =>
    request<null>(`/admin/allowed-emails/${id}`, { method: "DELETE" }),

  // ── Rôles des utilisateurs (#115) ──────────────────────────────────────────
  // Trois pouvoirs distincts : `users:read` pour la liste, `roles:read` pour
  // l'inventaire, `roles:assign` pour les deux écritures. `organisation_id` est
  // omis : le backend retombe sur le seul club en base.
  listAdminUsers: () => request<AdminUser[]>("/admin/users"),
  listRoles: () => request<Role[]>("/admin/roles"),
  grantRole: (userId: number, roleId: number) =>
    request<AdminUser>(`/admin/users/${userId}/roles`, {
      method: "POST",
      body: JSON.stringify({ role_id: roleId }),
    }),
  revokeRole: (userId: number, roleId: number) =>
    request<null>(`/admin/users/${userId}/roles/${roleId}`, { method: "DELETE" }),
};

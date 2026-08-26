import { toQuery } from "@/lib/api/query";
import type {
  AdminActionLogPage,
  AdminAthlete,
  AdminAthleteUpdate,
  AdminCourseUpdate,
  AdminUser,
  AllowedEmail,
  AthleteBrief,
  AthleteDetail,
  AthleteSearchResult,
  AuthMethod,
  BatchLaunched,
  BatchReport,
  BatchRun,
  BenevoleAccessConfig,
  BenevoleAccessGenerated,
  CounterScope,
  CounterScopeEntry,
  CourseBrief,
  CourseDeletionImpact,
  CourseDetail,
  CourseMergeImpact,
  CourseMergeResult,
  CourseQuery,
  CourseReliability,
  ClubRosterRank,
  CourseSummary,
  CoursesWipeImpact,
  CoursesWipeResult,
  DuplicateCandidateList,
  EventPage,
  Feedback,
  FeedbackCounts,
  FeedbackCreate,
  FeedbackCreated,
  FeedbackUpdate,
  GeoEvent,
  Group,
  GroupDetail,
  Participation,
  ParticipationFilters,
  ParticipationsWipeImpact,
  ParticipationsWipeResult,
  PendingProvider,
  PermissionGroup,
  RescrapeLaunch,
  Role,
  RoleCreate,
  RoleUpdate,
  ScopeKind,
  ScrapedPreview,
  Season,
  SessionRevocation,
  SessionUser,
  SheetColumns,
  SiteAccessConfig,
  SiteAccessGenerated,
  ValidationQueueHistory,
} from "@/lib/types";

const BASE = "/api/v1";

/**
 * Erreur d'API porteuse de son statut HTTP.
 *
 * Sans lui, un 401 était indiscernable d'un 500 : les deux arrivaient en `Error`
 * nu. La session en dépend — « pas connecté » est un état normal de la page, pas
 * une panne à signaler. Reste une `Error`, donc rien de l'existant ne change.
 *
 * `retryAfter` (secondes) ne vaut que pour un 429 : le plafond de débit
 * (`deps.py`) renvoie l'attente restante en en-tête `Retry-After`, et sans elle
 * un écran ne peut que dire « réessayez plus tard » là où il pourrait décompter.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly retryAfter: number | null;

  constructor(status: number, message: string, retryAfter: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfter = retryAfter;
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
export function messageDErreur(detail: unknown, repli: string): string {
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

/**
 * Envoi multipart — **distinct** de `request()`, et il doit le rester.
 *
 * `request()` pose `Content-Type: application/json` sur toutes ses requêtes.
 * Sur un `FormData`, cet en-tête empêche le navigateur d'écrire la frontière
 * (`boundary=…`) qu'il génère, et le serveur ne sait plus découper le corps :
 * le fichier arrive vide, sans qu'aucune erreur ne le dise. On ne pose donc
 * **aucun** `Content-Type` ici — c'est au navigateur de le composer.
 */
async function upload<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, messageDErreur(err.detail, res.statusText));
  }
  return res.json() as Promise<T>;
}

export const apiClient = {
  // `supported` vient du registre backend : le front ne tient aucune liste de
  // providers (la sienne avait divergé, cf. ProviderDetector).
  detectProvider: (url: string) =>
    request<{ provider: string; supported: boolean }>(
      `/scrape/detect${toQuery({ url })}`,
    ),

  // Même registre, même ordre de détection : le sélecteur de fournisseur du
  // batch ne peut donc proposer que des noms que le lancement accepte.
  listProviders: () =>
    request<{ providers: string[] }>("/scrape/providers").then((r) => r.providers),

  saveParticipation: (data: Partial<ScrapedPreview>) =>
    request<Participation>("/participations", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listParticipations: (filters: ParticipationFilters = {}) =>
    request<Participation[]>(`/participations${toQuery(filters as Record<string, unknown>)}`),

  // Rang exact d'un athlète dans le roster club, au-delà de l'aperçu de 12
  // (#504, #641) — appelé côté client, jamais transporté dans la page
  // (`RosterApercu`, seul appelant, ne le demande que si l'athlète retenu en
  // sort). `null` sur 404 : hors roster est un état normal, pas une panne.
  getClubRosterRank: async (
    athleteId: number,
    opts: { federal_only?: boolean } = {},
  ): Promise<ClubRosterRank | null> => {
    try {
      return await request<ClubRosterRank>(
        `/club/roster/rank/${athleteId}${toQuery(opts as Record<string, unknown>)}`,
      );
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },

  // Premier appel navigateur de cette route : `/athletes/{id}` n'était jusqu'ici
  // lu que par le rendu serveur de la fiche athlète. La bande « Ma saison »
  // (#502) l'appelle côté client, parce que l'athlète retenu vit en
  // `localStorage` et ne franchit pas la frontière serveur (#467).
  getAthlete: (
    id: number,
    filters: { seasons?: string; federal_only?: boolean } = {},
  ) => request<AthleteDetail>(`/athletes/${id}${toQuery(filters)}`),

  // Palette ⌘K (#484) — distincte de `listParticipations` : interroge les
  // athlètes directement (classés par pertinence côté backend), plus
  // l'agrégation de participations plafonnée à 100 lignes qui pouvait faire
  // disparaître un athlète peu couru sur un patronyme fréquent.
  searchAthletes: (q: string, limit = 13) =>
    request<AthleteSearchResult[]>(`/athletes/search${toQuery({ q, limit })}`),

  // Route du router public, et non `/admin/…` : elle y était déjà avant #439,
  // gardée par `participations:delete` (#115). La déplacer casserait un contrat
  // `/api/v1` publié pour un simple rangement (Principe IV).
  deleteParticipation: (id: number) =>
    request<null>(`/participations/${id}`, { method: "DELETE" }),

  getCourse: (id: number, opts: CourseQuery = {}) =>
    request<CourseDetail>(`/courses/${id}${toQuery(opts as Record<string, unknown>)}`),
  getCourseSummary: (id: number) => request<CourseSummary>(`/courses/${id}/summary`),

  listEvents: (filters: ParticipationFilters = {}) =>
    request<EventPage>(`/courses/events${toQuery(filters as Record<string, unknown>)}`),

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
      // `true` seul, jamais `false` : `toQuery` sérialise tout ce qui n'est ni
      // `undefined`, ni `null`, ni `""` — un `false` partirait en
      // `?unreliable=false` et brouillerait les clés de cache pour rien.
      unreliable?: true;
      page?: number;
      page_size?: number;
    } = {},
  ) => request<CourseBrief[]>(`/courses${toQuery(opts)}`),
  countCourses: (
    opts: {
      name?: string;
      event_type?: string;
      date_from?: string;
      date_to?: string;
      unreliable?: true;
    } = {},
  ) => request<{ total: number }>(`/courses/count${toQuery(opts)}`),
  getCourseDeletionImpact: (id: number) =>
    request<CourseDeletionImpact>(`/admin/courses/${id}/deletion-impact`),
  deleteCourse: (id: number) =>
    request<null>(`/admin/courses/${id}`, { method: "DELETE" }),

  // ── Purge totale des résultats (#384) ──────────────────────────────────────
  // `participations:wipe_all`. Vide `participations` entièrement ; `courses`
  // et `course_sources` restent intacts — c'est ce qui permet un rescrape
  // immédiat sans tout réimporter depuis les URLs sources.
  getParticipationsWipeImpact: () =>
    request<ParticipationsWipeImpact>("/admin/participations/wipe-impact"),
  // Rend le décompte réel depuis #501 — la route ne rendait qu'un 204 vide.
  wipeAllParticipations: () =>
    request<ParticipationsWipeResult>("/admin/participations", { method: "DELETE" }),

  // ── Purge totale des épreuves (#384, suite) ─────────────────────────────────
  // `courses:wipe_all`. Strictement plus destructeur que ci-dessus : les
  // épreuves elles-mêmes et leurs sources disparaissent aussi.
  getCoursesWipeImpact: () => request<CoursesWipeImpact>("/admin/courses/wipe-impact"),
  wipeAllCourses: () =>
    request<CoursesWipeResult>("/admin/courses", { method: "DELETE" }),

  updateCourse: (id: number, champs: Partial<AdminCourseUpdate>) =>
    request<CourseBrief>(`/admin/courses/${id}`, {
      method: "PATCH",
      body: JSON.stringify(champs),
    }),

  // ── Journal d'administration (#501) ─────────────────────────────────────────
  getActionLog: (page: number, pageSize: number) =>
    request<AdminActionLogPage>(`/admin/action-log${toQuery({ page, page_size: pageSize })}`),

  // ── Revalidation qualité (#119) ────────────────────────────────────────────
  // `quality:override`. `reliability_override: null` **lève** l'avis humain et
  // fait reprendre le verdict calculé ; `notes` motive la décision au journal.
  setCourseReliability: (
    id: number,
    body: { reliability_override: boolean | null; notes?: string },
  ) =>
    request<CourseReliability>(`/admin/courses/${id}/reliability`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  // Bascule de la source active (#285) : flux SSE depuis #624
  // (`switchSourceEventStream`, `lib/api/sse.ts`) — plus un appel `request()`
  // classique, le remplacement peut durer plusieurs dizaines de secondes sur
  // une épreuve fan-out.
  listCourseDuplicates: () => request<DuplicateCandidateList>("/admin/courses/duplicates"),
  getCourseMergeImpact: (courseId: number, absorbedId: number) =>
    request<CourseMergeImpact>(
      `/admin/courses/${courseId}/merge-impact${toQuery({ absorbed_id: absorbedId })}`,
    ),
  /** Ne re-scrape rien (#287) : la cible garde son classement, l'absorbée est détruite. */
  mergeCourses: (courseId: number, absorbedId: number) =>
    request<CourseMergeResult>(`/admin/courses/${courseId}/merge`, {
      method: "POST",
      body: JSON.stringify({ absorbed_id: absorbedId }),
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

  // ── Batches (#47) ──────────────────────────────────────────────────────────
  // Deux pouvoirs : `batch:run` pour le lancement, `batch:read` pour le suivi.
  // La base visée n'est **jamais** envoyée — elle vient du réglage de
  // l'instance, et le backend refuse en 422 un `target` reçu du client.
  launchBatch: (options: RescrapeLaunch) =>
    request<BatchLaunched>("/admin/batches", {
      method: "POST",
      body: JSON.stringify(options),
    }),
  listBatchRuns: (limit = 20) =>
    request<BatchRun[]>(`/admin/batches${toQuery({ limit })}`),
  getBatchReport: (runId: number) =>
    request<BatchReport>(`/admin/batches/${runId}/report`),
  // Le fichier fait **deux** allers : le navigateur le garde entre les deux, il
  // n'est jamais stocké côté serveur (FR-011).
  readSheetColumns: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return upload<SheetColumns>("/admin/sheets/columns", form);
  },
  launchBatchFromFile: (file: File, urlColumn: number, dryRun: boolean) => {
    const form = new FormData();
    form.append("file", file);
    form.append("url_column", String(urlColumn));
    form.append("dry_run", String(dryRun));
    return upload<BatchLaunched>("/admin/batches/from-file", form);
  },
  // ── Groupes d'appartenance (#197) ──────────────────────────────────────────
  // Trois pouvoirs : `groups:read` pour les deux lectures, `groups:write` pour
  // le cycle de vie du groupe, `groups:assign` pour sa composition. `slug` n'est
  // pas modifiable — le soumettre à `PATCH` rend 422, jamais un renommage
  // silencieux.
  listGroups: () => request<Group[]>("/admin/groups"),
  getGroup: (id: number) => request<GroupDetail>(`/admin/groups/${id}`),
  createGroup: (body: { slug: string; name: string; description: string }) =>
    request<GroupDetail>("/admin/groups", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateGroup: (id: number, champs: { name?: string; description?: string }) =>
    request<GroupDetail>(`/admin/groups/${id}`, {
      method: "PATCH",
      body: JSON.stringify(champs),
    }),
  deleteGroup: (id: number) =>
    request<null>(`/admin/groups/${id}`, { method: "DELETE" }),
  addGroupMember: (groupId: number, userId: number) =>
    request<GroupDetail>(`/admin/groups/${groupId}/members`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId }),
    }),
  removeGroupMember: (groupId: number, userId: number) =>
    request<null>(`/admin/groups/${groupId}/members/${userId}`, { method: "DELETE" }),
  // ── Composition des rôles (#115, écran #240) ───────────────────────────────
  // Lecture sous `roles:read`, écriture sous `roles:write`. `listRoles` est
  // celle de l'attribution ci-dessus — même ressource, même cache.
  // `GET /admin/roles/{id}` n'est pas exposée : la liste rend déjà des rôles
  // complets, la demander par rôle ne rendrait rien de neuf.
  listPermissions: () => request<PermissionGroup[]>("/admin/permissions"),
  createRole: (body: RoleCreate) =>
    request<Role>("/admin/roles", { method: "POST", body: JSON.stringify(body) }),
  // `champs` est partiel **par contrat** : `permissions` remplace l'ensemble,
  // donc l'envoyer sans qu'il ait changé purgerait les codes périmés du rôle.
  updateRole: (id: number, champs: RoleUpdate) =>
    request<Role>(`/admin/roles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(champs),
    }),
  deleteRole: (id: number) => request<null>(`/admin/roles/${id}`, { method: "DELETE" }),

  // ── Révocation d'urgence des sessions (#169) ───────────────────────────────
  // `sessions:revoke`. Sans corps : la ressource est **globale**, fermer les
  // sessions d'un seul compte se fait en retirant son adresse (#170). Elle ferme
  // aussi celle de l'appelant — la requête suivante rendra 401, par construction.
  // Une ressource, deux portées : sans adresse elle ferme **tout** (la session
  // de l'appelant comprise), avec une adresse elle ferme **tous** les comptes
  // qui la portent — `users.email` n'est pas unique, et l'écran des accès liste
  // des adresses, pas des comptes. Même cible que la CLI.
  revokeSessions: (email?: string) =>
    request<SessionRevocation>("/admin/sessions/revoke", {
      method: "POST",
      body: JSON.stringify(email === undefined ? {} : { email }),
    }),

  // ── Mot de passe partagé bénévoles (#271 → cette feature) ─────────────────
  // `benevole_access:manage`. `PUT`/`generate` rendent la même forme que `GET`,
  // sauf `generate` qui ajoute le mot de passe en clair — une seule fois.
  getBenevoleAccessConfig: () =>
    request<BenevoleAccessConfig>("/admin/benevoles/access"),
  replaceBenevoleAccessPassword: (password: string) =>
    request<BenevoleAccessConfig>("/admin/benevoles/access", {
      method: "PUT",
      body: JSON.stringify({ password }),
    }),
  generateBenevoleAccessPassword: () =>
    request<BenevoleAccessGenerated>("/admin/benevoles/access/generate", {
      method: "POST",
    }),

  // ── Mot de passe d'accès au site (#509) ────────────────────────────────────
  siteAccessLogin: (password: string) =>
    request<null>("/site-access/session", { method: "POST", body: JSON.stringify({ password }) }),
  // `site_access:manage`. `PUT`/`generate` rendent la même forme que `GET`,
  // sauf `generate` qui ajoute le mot de passe en clair — une seule fois.
  getSiteAccessConfig: () => request<SiteAccessConfig>("/admin/site-access"),
  replaceSiteAccessPassword: (password: string) =>
    request<SiteAccessConfig>("/admin/site-access", {
      method: "PUT",
      body: JSON.stringify({ password }),
    }),
  generateSiteAccessPassword: () =>
    request<SiteAccessGenerated>("/admin/site-access/generate", { method: "POST" }),

  // ── Portée des compteurs (#95) ─────────────────────────────────────────────
  // Une seule lecture pour les deux listes : l'écran les affiche ensemble, deux
  // appels seraient deux allers-retours pour une page.
  getCounterScope: () => request<CounterScope>("/admin/counter-scope"),
  addCounterScopeEntry: (kind: ScopeKind, value: string) =>
    request<CounterScopeEntry>(`/admin/counter-scope/${kind}`, {
      method: "POST",
      body: JSON.stringify({ value }),
    }),
  // L'entrée est désignée par son identifiant, jamais par sa valeur : un
  // libellé porte des espaces, et le faire transiter par un segment d'URL est
  // une source d'ennuis sans contrepartie.
  removeCounterScopeEntry: (kind: ScopeKind, entryId: number) =>
    request<void>(`/admin/counter-scope/${kind}/${entryId}`, { method: "DELETE" }),

  // ── Retours utilisateurs (#267) ────────────────────────────────────────────
  // Route publique, et son chemin le dit : `/feedback`, hors de `/admin` où
  // vivent les trois verbes gardés de la même ressource. Aucune session requise ;
  // l'email de l'émetteur, si connecté, est déduit côté serveur du cookie —
  // jamais un champ de ce corps.
  submitFeedback: (body: FeedbackCreate) =>
    request<FeedbackCreated>("/feedback", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  // Lecture réservée `feedback:read`. Pas de pagination dans cette v1
  // (contracts/feedback-api.md — volume attendu modeste). `status` est
  // facultatif : omis, la route rend toute la table, sa forme d'origine.
  listFeedback: (
    sort: "created_at" | "type" | "status",
    order: "asc" | "desc",
    status?: Feedback["status"],
  ) => request<Feedback[]>(`/admin/feedback${toQuery({ sort, order, status })}`),
  // Le compteur de la file (#500) — une route à part, comme `/courses/count` :
  // loger des totaux dans la liste changerait la forme publiée de v1.
  countFeedback: () => request<FeedbackCounts>("/admin/feedback/counts"),
  getFeedback: (id: number) => request<Feedback>(`/admin/feedback/${id}`),
  // `feedback:manage`. `champs` est partiel par contrat — même convention que
  // `updateRole` : n'envoyer que ce qui a changé.
  updateFeedbackStatus: (id: number, champs: Partial<FeedbackUpdate>) =>
    request<Feedback>(`/admin/feedback/${id}`, {
      method: "PATCH",
      body: JSON.stringify(champs),
    }),
  updateFeedbackGithubUrl: (id: number, githubUrl: string) =>
    request<Feedback>(`/admin/feedback/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ github_url: githubUrl }),
    }),

  // ── Page de vérification des résultats par les bénévoles (#271) ────────────
  // Garde par mot de passe partagé (`require_benevole_access`), **pas** par
  // pouvoir SSO/RBAC — research.md §D1 de la feature. `benevoleLogin` répond
  // 401 sur un mot de passe incorrect ou non configuré ; les quatre autres
  // répondent 401 sans le cookie que `benevoleLogin` pose.
  //
  // `searchAthletesBenevole` visait `GET /athletes` jusqu'à #513 : cette route
  // est passée derrière le mot de passe du site (#509), que cette population
  // n'a pas — 401 avalé en « aucun coureur trouvé ». Sa jumelle sous
  // `/benevoles/` porte la garde de la page qui l'appelle. Ne pas la remplacer
  // par `searchAthletesAdmin` : celle-ci rend la date de naissance.
  searchAthletesBenevole: (name: string) =>
    request<AthleteBrief[]>(`/benevoles/athletes${toQuery({ name })}`),
  benevoleLogin: (password: string) =>
    request<null>("/benevoles/session", { method: "POST", body: JSON.stringify({ password }) }),
  benevoleLogout: () => request<null>("/benevoles/session", { method: "DELETE" }),
  getBenevoleQueue: () => request<Participation[]>("/benevoles/queue"),
  getValidationQueueHistory: () => request<ValidationQueueHistory>("/benevoles/queue/history"),
  validateParticipationBenevole: (participationId: number) =>
    request<Participation>(`/benevoles/participations/${participationId}/validate`, {
      method: "POST",
    }),
  renameCourseBenevole: (courseId: number, name: string) =>
    request<CourseBrief>(`/benevoles/courses/${courseId}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  reassignParticipationBenevole: (participationId: number, athleteId: number) =>
    request<Participation>(`/benevoles/participations/${participationId}/reassign`, {
      method: "POST",
      body: JSON.stringify({ athlete_id: athleteId }),
    }),
  getBenevoleRejected: () => request<Participation[]>("/benevoles/rejected"),
  rejectParticipationBenevole: (participationId: number) =>
    request<Participation>(`/benevoles/participations/${participationId}/reject`, {
      method: "POST",
    }),
  unrejectParticipationBenevole: (participationId: number) =>
    request<Participation>(`/benevoles/participations/${participationId}/unreject`, {
      method: "POST",
    }),
  updateParticipationFieldsBenevole: (
    participationId: number,
    champs: { bib_number?: string | null; rank_overall?: number | null; club?: string | null; category?: string | null },
  ) =>
    request<Participation>(`/benevoles/participations/${participationId}`, {
      method: "PATCH",
      body: JSON.stringify(champs),
    }),
};

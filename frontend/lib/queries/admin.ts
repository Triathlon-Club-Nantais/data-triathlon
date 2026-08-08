import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";
import type {
  AdminAthleteUpdate,
  AdminCourseUpdate,
  RoleCreate,
  RoleUpdate,
} from "@/lib/types";

export function usePendingProviders() {
  return useQuery({
    queryKey: queryKeys.pendingProviders(),
    queryFn: () => apiClient.listPendingProviders(),
  });
}

export function useMarkProviderHandled() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.markProviderHandled(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.pendingProviders() }),
  });
}

export function useAllowedEmails() {
  return useQuery({
    queryKey: queryKeys.allowedEmails(),
    queryFn: () => apiClient.listAllowedEmails(),
  });
}

export function useAddAllowedEmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ email, roleId }: { email: string; roleId?: number | null }) =>
      apiClient.addAllowedEmail(email, roleId),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.allowedEmails() }),
  });
}

export function useRemoveAllowedEmail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.removeAllowedEmail(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.allowedEmails() }),
  });
}

// ── Administration des données (#117) ────────────────────────────────────────

/**
 * Les caches qu'un geste correctif périme, par leur préfixe de clé.
 *
 * `admin-course-detail` est le plus facile à oublier et le plus visible : c'est
 * lui que lit la liste des résultats d'une épreuve, et une correction de coureur
 * ou un rattachement y laisserait l'ancien nom affiché jusqu'à ce qu'on ferme la
 * modale. Invalider large est ici moins coûteux qu'une liste qui ment.
 */
const CACHES_ADMIN = {
  courses: ["admin-courses"] as const,
  detailEpreuve: ["admin-course-detail"] as const,
  coureurs: ["admin-athletes"] as const,
  ficheCoureur: ["admin-athlete"] as const,
  resultatsPublics: ["course-participations"] as const,
};

/** Le catalogue d'épreuves, tel que le sert la lecture publique. */
export const TAILLE_PAGE_ADMIN = 20;

/** Les filtres du catalogue, tels que `GET /courses` les accepte. */
export type FiltresCourses = {
  name?: string;
  event_type?: string;
  date_from?: string;
  date_to?: string;
};

export function useAdminCourses(page = 1, filtres: FiltresCourses = {}) {
  return useQuery({
    queryKey: queryKeys.adminCourses(page, filtres as Record<string, string>),
    queryFn: () =>
      apiClient.listCourses({ ...filtres, page, page_size: TAILLE_PAGE_ADMIN }),
    placeholderData: (precedent) => precedent,
  });
}

/**
 * Le total du catalogue aux mêmes filtres — le « sur 7 » de la pagination.
 *
 * Clé **sans la page** : feuilleter ne redemande pas un total qui ne bouge pas.
 */
export function useAdminCoursesCount(filtres: FiltresCourses = {}) {
  return useQuery({
    queryKey: queryKeys.adminCoursesCount(filtres as Record<string, string>),
    queryFn: () => apiClient.countCourses(filtres),
    placeholderData: (precedent) => precedent,
  });
}

/**
 * Ce que la suppression détruirait — chargé **à l'ouverture de la modale**.
 *
 * `enabled` plutôt qu'un appel au montage : une liste de cinquante épreuves ne
 * doit pas déclencher cinquante chiffrages d'impact pour un geste qui n'aura
 * peut-être pas lieu.
 */
export function useCourseDeletionImpact(courseId: number | null) {
  return useQuery({
    queryKey: queryKeys.courseDeletionImpact(courseId ?? 0),
    queryFn: () => apiClient.getCourseDeletionImpact(courseId as number),
    enabled: courseId !== null,
    retry: false,
  });
}

export function useDeleteCourse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.deleteCourse(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.courses });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
    },
  });
}

/**
 * Recherche de coureurs réservée — la seule lecture qui rend une date de naissance.
 *
 * `enabled` sur une saisie non vide : sans lui, l'ouverture d'une modale
 * déclencherait une recherche à blanc qui ramènerait les vingt premiers
 * coureurs de la base, sans rapport avec ce que l'administrateur cherche.
 */
export function useAdminAthleteSearch(search: string) {
  return useQuery({
    queryKey: queryKeys.adminAthletes(search),
    queryFn: () => apiClient.searchAthletesAdmin(search),
    enabled: search.trim().length > 0,
  });
}

/**
 * La fiche **complète** d'un coureur, chargée avant d'ouvrir son édition.
 *
 * Un résultat ne porte qu'un `AthleteBrief`, sans date de naissance. Ouvrir
 * l'édition avec cette fiche tronquée puis enregistrer effacerait une date que
 * l'écran n'a jamais lue — une perte de données silencieuse.
 */
export function useAdminAthlete(id: number | null) {
  return useQuery({
    queryKey: queryKeys.adminAthlete(id ?? 0),
    queryFn: () => apiClient.getAthleteAdmin(id as number),
    enabled: id !== null,
  });
}

export function useReassignParticipation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ participationId, athleteId }: { participationId: number; athleteId: number }) =>
      apiClient.reassignParticipation(participationId, athleteId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.resultatsPublics });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.coureurs });
    },
  });
}

export function useUpdateCourse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, champs }: { id: number; champs: Partial<AdminCourseUpdate> }) =>
      apiClient.updateCourse(id, champs),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.courses });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
    },
  });
}

export function useUpdateAthlete() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, champs }: { id: number; champs: Partial<AdminAthleteUpdate> }) =>
      apiClient.updateAthlete(id, champs),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.coureurs });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.ficheCoureur });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.resultatsPublics });
    },
  });
}

// ── Rôles des utilisateurs (#239) ────────────────────────────────────────────

export function useAdminUsers() {
  return useQuery({
    queryKey: queryKeys.adminUsers(),
    queryFn: () => apiClient.listAdminUsers(),
  });
}

/**
 * La liste des rôles, **partagée** par l'attribution (#239) et la composition
 * (#240). Une seconde clé donnerait deux caches de la même ressource, dont l'un
 * afficherait un nom ou un `holders` que l'autre vient de changer.
 */
export function useRoles() {
  return useQuery({
    queryKey: queryKeys.roles(),
    queryFn: () => apiClient.listRoles(),
    // `/admin/acces` lit l'inventaire pour son sélecteur alors que sa propre
    // garde est `allowed_emails:manage` : un porteur de ce seul pouvoir prend un
    // 403 ici. Le réessayer trois fois n'y changera rien.
    retry: false,
  });
}

/**
 * Les deux écritures invalident **aussi** `roles()` : `RoleRead.holders` compte
 * les porteurs, et l'écran voisin (#240) l'affiche.
 */
export function useGrantRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: number; roleId: number }) =>
      apiClient.grantRole(userId, roleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.adminUsers() });
      qc.invalidateQueries({ queryKey: queryKeys.roles() });
    },
  });
}

export function useRevokeRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleId }: { userId: number; roleId: number }) =>
      apiClient.revokeRole(userId, roleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.adminUsers() });
      qc.invalidateQueries({ queryKey: queryKeys.roles() });
    },
  });
}

// ── Composition des rôles (#115, écran #240) ─────────────────────────────────

/**
 * L'inventaire des pouvoirs, **déjà regroupé par fonctionnalité** par le serveur.
 *
 * `staleTime: Infinity` : il est servi depuis le code Python
 * (`core/permissions.py`), sans table ni migration — il ne peut changer qu'au
 * déploiement, et le redemander pendant une session ne rendrait jamais rien de
 * neuf.
 *
 * `retry: false`, comme `useRoles` : un 403 est une réponse, pas une panne. Le
 * réessayer trois fois retarde d'autant le message d'accès refusé.
 */
export function useAdminPermissions() {
  return useQuery({
    queryKey: queryKeys.adminPermissions(),
    queryFn: () => apiClient.listPermissions(),
    staleTime: Infinity,
    retry: false,
  });
}

/**
 * Les trois gestes de composition périment **les rôles, la session et les
 * utilisateurs**.
 *
 * La session, parce que recomposer un rôle qu'on porte soi-même est le cas
 * nominal — c'est le seul rôle qu'un administrateur ait toujours sous la main.
 * Sans elle, `session.permissions` reste sur l'ancien état et la grille continue
 * de figer des cases que l'on porte désormais.
 *
 * Les utilisateurs, parce que `UserRolesTable` (#239) affiche le **nom** des
 * rôles attribués : c'est le symétrique exact de ce que font `useGrantRole` et
 * `useRevokeRole` sur `roles()` pour le compte de porteurs.
 */
function useRoleMutation<TVariables, TData>(
  mutationFn: (variables: TVariables) => Promise<TData>,
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.roles() });
      qc.invalidateQueries({ queryKey: queryKeys.session() });
      qc.invalidateQueries({ queryKey: queryKeys.adminUsers() });
    },
  });
}

export function useCreateRole() {
  return useRoleMutation((body: RoleCreate) => apiClient.createRole(body));
}

export function useUpdateRole() {
  return useRoleMutation(({ id, champs }: { id: number; champs: RoleUpdate }) =>
    apiClient.updateRole(id, champs),
  );
}

export function useDeleteRole() {
  return useRoleMutation((id: number) => apiClient.deleteRole(id));
}

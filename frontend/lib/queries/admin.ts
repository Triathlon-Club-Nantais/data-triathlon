import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";
import type { AdminAthleteUpdate, AdminCourseUpdate } from "@/lib/types";

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

// ── Révocation d'urgence des sessions (#169) ─────────────────────────────────

/**
 * Invalide la **session**, comme `useLogout` — le geste ferme aussi celle de
 * l'appelant.
 *
 * On avait d'abord cru qu'il ne fallait rien invalider, « tout refetch rendant
 * 401 ». C'est faux là où ça compte : `useSession` traduit un 401 en `null`,
 * par contrat, et le refetch donne donc l'état anonyme correct. Sans lui, la
 * navigation client vers `/login` laisse `AppNav` et `UserMenu` montés dans le
 * layout racine, avec le nom, l'avatar et tout le menu d'administration — un
 * écran d'apparence connectée, exactement ce que le composant dit éviter.
 */
export function useRevokeAllSessions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.revokeAllSessions(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.session() }),
  });
}

/**
 * Révocation durable d'**un** compte (#169).
 *
 * Invalide aussi la session : le geste est permis sur soi-même — c'est celui de
 * « j'ai perdu mon téléphone » —, et sans cette ligne la topbar resterait
 * connectée alors que la requête suivante rendrait 401.
 */
export function useRevokeUserSessions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) => apiClient.revokeUserSessions(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.adminUsers() });
      qc.invalidateQueries({ queryKey: queryKeys.session() });
    },
  });
}

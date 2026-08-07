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
    mutationFn: (email: string) => apiClient.addAllowedEmail(email),
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
export const TAILLE_PAGE_ADMIN = 50;

export function useAdminCourses(page = 1) {
  return useQuery({
    queryKey: queryKeys.adminCourses(page),
    queryFn: () =>
      apiClient.listCourses({ page, page_size: TAILLE_PAGE_ADMIN }),
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

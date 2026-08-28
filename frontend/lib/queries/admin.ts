import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";
import type {
  AdminAthleteUpdate,
  AdminCourseUpdate,
  Feedback,
  RoleCreate,
  RoleUpdate,
  ScopeKind,
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
  /** Filtre exact par identifiant d'épreuve (#718). */
  id?: string;
  name?: string;
  event_type?: string;
  date_from?: string;
  date_to?: string;
  /** La file de revalidation (#119). `true` seul — voir `client.listCourses`. */
  unreliable?: true;
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
 *
 * `actif` sert le badge de navigation (#119), monté sur **toutes** les pages :
 * sans lui, chaque visiteur paierait un comptage qu'il n'a pas le droit de voir.
 */
export function useAdminCoursesCount(filtres: FiltresCourses = {}, actif = true) {
  return useQuery({
    queryKey: queryKeys.adminCoursesCount(filtres as Record<string, string>),
    queryFn: () => apiClient.countCourses(filtres),
    placeholderData: (precedent) => precedent,
    enabled: actif,
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
 * Ce qu'une purge totale des résultats détruirait — chargé **à l'ouverture
 * de la modale** (#384), même patron que `useCourseDeletionImpact`.
 */
export function useParticipationsWipeImpact(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.participationsWipeImpact(),
    queryFn: () => apiClient.getParticipationsWipeImpact(),
    enabled,
    retry: false,
  });
}

/**
 * La purge totale des résultats (#384). Invalide tout ce qu'un résultat
 * alimente : le catalogue d'épreuves (leur `scraped_at` vient de changer),
 * le détail d'une épreuve, la liste et les fiches coureur, et les résultats
 * publics.
 *
 * **Son propre chiffrage en fait partie**, et c'est le plus facile à oublier :
 * sans lui, rouvrir la modale après une purge repeindrait les comptes d'avant
 * — donnée en cache, `isLoading` à `false`, donc pas même un squelette pour
 * signaler qu'elle est périmée.
 */
export function useWipeAllParticipations() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.wipeAllParticipations(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.participationsWipeImpact() });
      // Symétrique de `useWipeAllCourses` : le chiffrage de l'autre purge lit
      // aussi `participations`, une modale restée en cache mentirait pareil.
      qc.invalidateQueries({ queryKey: queryKeys.coursesWipeImpact() });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.courses });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.coureurs });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.ficheCoureur });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.resultatsPublics });
      qc.invalidateQueries({ queryKey: queryKeys.courseDuplicates() });
    },
  });
}

/**
 * Ce qu'une purge totale des épreuves détruirait — même patron que
 * `useParticipationsWipeImpact` (#384, suite).
 */
export function useCoursesWipeImpact(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.coursesWipeImpact(),
    queryFn: () => apiClient.getCoursesWipeImpact(),
    enabled,
    retry: false,
  });
}

/**
 * La purge totale des épreuves (#384, suite). Emporte aussi les résultats
 * (`DELETE` de masse côté backend, enfants d'abord), donc invalide les deux
 * chiffrages — le sien et celui de `useWipeAllParticipations` — en plus des
 * mêmes caches. `courseDuplicates` aussi : le catalogue vidé, la liste de
 * doublons suspects ne peut plus contenir que des entrées fantômes.
 */
export function useWipeAllCourses() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.wipeAllCourses(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.coursesWipeImpact() });
      qc.invalidateQueries({ queryKey: queryKeys.participationsWipeImpact() });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.courses });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.coureurs });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.ficheCoureur });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.resultatsPublics });
      qc.invalidateQueries({ queryKey: queryKeys.courseDuplicates() });
    },
  });
}

// Bascule de la source active d'une épreuve (#285, #291) : flux SSE depuis
// #624 (`useSwitchSourceStream`, `hooks/useSwitchSourceStream.ts`), état géré
// à la main comme `useRescrapeStream` — pas de mutation React Query ici,
// patron identique et même raison (research.md R1 : un seul consommateur, le
// navigateur qui a cliqué).

/** Doublons suspects entre épreuves (#288), pour le panel d'administration (#292). */
export function useCourseDuplicates() {
  return useQuery({
    queryKey: queryKeys.courseDuplicates(),
    queryFn: () => apiClient.listCourseDuplicates(),
  });
}

/**
 * Ce qu'une fusion emporterait — chargé **à la sélection de la cible**, sur le
 * même patron que `useCourseDeletionImpact` : tant que l'administrateur n'a
 * pas choisi quelle épreuve des deux survit, il n'y a rien à chiffrer.
 */
export function useCourseMergeImpact(courseId: number | null, absorbedId: number | null) {
  return useQuery({
    queryKey: queryKeys.courseMergeImpact(courseId ?? 0, absorbedId ?? 0),
    queryFn: () => apiClient.getCourseMergeImpact(courseId as number, absorbedId as number),
    enabled: courseId !== null && absorbedId !== null,
    retry: false,
  });
}

/** Fusion de deux épreuves (#287) : la paire fusionnée doit sortir de la liste des doublons. */
export function useMergeCourses() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ courseId, absorbedId }: { courseId: number; absorbedId: number }) =>
      apiClient.mergeCourses(courseId, absorbedId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.courseDuplicates() });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.courses });
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

/**
 * Suppression d'**un** résultat (#439).
 *
 * Mêmes invalidations que `useReassignParticipation` : le geste change les mêmes
 * écrans — les résultats publics, le détail de l'épreuve et la liste des
 * coureurs, dont les compteurs de participations bougent.
 */
export function useDeleteParticipation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (participationId: number) => apiClient.deleteParticipation(participationId),
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

/**
 * Trancher la fiabilité d'une épreuve (#119, `quality:override`).
 *
 * `verdict: null` **lève** l'avis humain. L'invalidation de « admin-courses »
 * suffit à faire sortir la ligne de la file : la file n'est qu'une vue filtrée
 * du catalogue, il n'y a aucune seconde liste à tenir à jour (AC4).
 *
 * `resultatsPublics` aussi, même raison que `useUpdateAthlete` : `is_reliable`
 * pilote un marqueur sur la fiche athlète (`app/athletes/[id]/page.tsx`), qui
 * resterait périmé jusqu'au prochain montage sans cette invalidation.
 */
export function useSetCourseReliability() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      courseId,
      verdict,
      notes,
    }: {
      courseId: number;
      verdict: boolean | null;
      notes?: string;
    }) =>
      apiClient.setCourseReliability(courseId, {
        reliability_override: verdict,
        ...(notes ? { notes } : {}),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.courses });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.resultatsPublics });
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
    // Même raison que `useRoles` : l'écran des groupes (#241) lit cette liste
    // pour choisir qui ajouter, alors que sa propre garde est `groups:assign`.
    // Un porteur de ce seul pouvoir prend un 403 ici, que trois essais ne
    // changeront pas.
    retry: false,
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

// ── Révocation d'urgence des sessions (#169) ─────────────────────────────────

/**
 * Ferme des sessions : toutes sans argument, celles d'une adresse sinon.
 *
 * Invalide la **session**, comme `useLogout`. On avait d'abord cru qu'il ne
 * fallait rien invalider, « tout refetch rendant 401 ». C'est faux là où ça
 * compte : `useSession` traduit un 401 en `null`, par contrat, et le refetch
 * donne donc l'état anonyme correct. Sans lui, la navigation client vers
 * `/login` laisse `AppNav` et `UserMenu` montés dans le layout racine, avec le
 * nom, l'avatar et tout le menu d'administration — un écran d'apparence
 * connectée, exactement ce qu'on cherche à éviter.
 *
 * Invalide aussi la liste des accès : `has_account` n'y bouge pas, mais une
 * portée d'adresse peut viser sa propre adresse, et la ligne doit se relire
 * dans le même état que la topbar.
 */
export function useRevokeSessions() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (email?: string) => apiClient.revokeSessions(email),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.session() });
      qc.invalidateQueries({ queryKey: queryKeys.allowedEmails() });
    },
  });
}

// ── Mot de passe partagé bénévoles (#271 → cette feature) ───────────────────

export function useBenevoleAccessConfig() {
  return useQuery({
    queryKey: queryKeys.benevoleAccessConfig(),
    queryFn: () => apiClient.getBenevoleAccessConfig(),
    retry: false,
  });
}

export function useReplaceBenevoleAccessPassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => apiClient.replaceBenevoleAccessPassword(password),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.benevoleAccessConfig() }),
  });
}

export function useGenerateBenevoleAccessPassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.generateBenevoleAccessPassword(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.benevoleAccessConfig() }),
  });
}

// ── Mot de passe d'accès au site (#509) ──────────────────────────────────────

export function useSiteAccessConfig() {
  return useQuery({
    queryKey: queryKeys.siteAccessConfig(),
    queryFn: () => apiClient.getSiteAccessConfig(),
    retry: false,
  });
}

export function useReplaceSiteAccessPassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => apiClient.replaceSiteAccessPassword(password),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.siteAccessConfig() }),
  });
}

export function useGenerateSiteAccessPassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.generateSiteAccessPassword(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.siteAccessConfig() }),
  });
}

// ── Portée des compteurs (#95) ───────────────────────────────────────────────

export function useCounterScope() {
  return useQuery({
    queryKey: queryKeys.counterScope(),
    queryFn: () => apiClient.getCounterScope(),
    retry: false,
  });
}

/**
 * Après une écriture, **tout** le cache est périmé — et c'est délibéré.
 *
 * Déclarer un libellé de club ou exclure une discipline change ce que chaque
 * compteur du site additionne : classements, tableaux de bord, badges, listes
 * filtrées. Énumérer les clés concernées reviendrait à tenir à jour, ici, la
 * liste de tous les écrans qui comptent quelque chose — une liste qui se
 * périmerait au prochain écran ajouté, en silence et en affichant des chiffres
 * d'avant la modification.
 *
 * Le coût est nul à l'échelle : ces écritures sont rares (quelques par an), et
 * elles ont lieu dans le back-office, pas sur un chemin chaud.
 */
function useInvalidationDeLaPorteeDesCompteurs() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries();
}

export function useAddCounterScopeEntry() {
  const toutPerimer = useInvalidationDeLaPorteeDesCompteurs();
  return useMutation({
    mutationFn: ({ kind, value }: { kind: ScopeKind; value: string }) =>
      apiClient.addCounterScopeEntry(kind, value),
    onSuccess: toutPerimer,
  });
}

export function useRemoveCounterScopeEntry() {
  const toutPerimer = useInvalidationDeLaPorteeDesCompteurs();
  return useMutation({
    mutationFn: ({ kind, entryId }: { kind: ScopeKind; entryId: number }) =>
      apiClient.removeCounterScopeEntry(kind, entryId),
    onSuccess: toutPerimer,
  });
}

// ── Groupes d'appartenance (#241) ────────────────────────────────────────────

export function useGroups() {
  return useQuery({
    queryKey: queryKeys.groups(),
    queryFn: () => apiClient.listGroups(),
  });
}

/**
 * La composition d'un groupe, chargée **à l'ouverture** de son détail.
 *
 * `enabled` plutôt qu'un appel au montage, comme pour l'impact d'une
 * suppression : une liste de dix groupes ne doit pas demander dix compositions
 * que personne ne regardera.
 */
export function useGroup(groupId: number | null) {
  return useQuery({
    queryKey: queryKeys.group(groupId ?? 0),
    queryFn: () => apiClient.getGroup(groupId as number),
    enabled: groupId !== null,
  });
}

/**
 * Les cinq écritures invalident la **liste**, et celles qui portent sur un
 * groupe précis invalident aussi son détail : `member_count` vit sur la liste,
 * `members` sur le détail, et un ajout déplace les deux.
 */
export function useCreateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (groupe: { slug: string; name: string; description: string }) =>
      apiClient.createGroup(groupe),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.groups() }),
  });
}

export function useUpdateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      champs,
    }: {
      id: number;
      champs: { name?: string; description?: string };
    }) => apiClient.updateGroup(id, champs),
    onSuccess: (_donnees, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.groups() });
      qc.invalidateQueries({ queryKey: queryKeys.group(id) });
    },
  });
}

export function useDeleteGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient.deleteGroup(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.groups() }),
  });
}

export function useAddGroupMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, userId }: { groupId: number; userId: number }) =>
      apiClient.addGroupMember(groupId, userId),
    onSuccess: (_donnees, { groupId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.groups() });
      qc.invalidateQueries({ queryKey: queryKeys.group(groupId) });
      // Et sa **propre** session : `GET /auth/me` rend `groups`, que le menu
      // utilisateur affiche. S'ajouter à un groupe sans la périmer laisserait
      // son propre menu mentir sur soi jusqu'au prochain rechargement.
      qc.invalidateQueries({ queryKey: queryKeys.session() });
    },
  });
}

export function useRemoveGroupMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, userId }: { groupId: number; userId: number }) =>
      apiClient.removeGroupMember(groupId, userId),
    onSuccess: (_donnees, { groupId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.groups() });
      qc.invalidateQueries({ queryKey: queryKeys.group(groupId) });
      // Et sa **propre** session : `GET /auth/me` rend `groups`, que le menu
      // utilisateur affiche. S'ajouter à un groupe sans la périmer laisserait
      // son propre menu mentir sur soi jusqu'au prochain rechargement.
      qc.invalidateQueries({ queryKey: queryKeys.session() });
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

// ── Retours utilisateurs (#267) ──────────────────────────────────────────────

/** `statut` à `"tous"` rend toute la table : la file affiche alors l'historique. */
export function useFeedbackList(
  sort: "created_at" | "type" | "status",
  order: "asc" | "desc",
  statut: Feedback["status"] | "tous",
) {
  return useQuery({
    queryKey: queryKeys.feedbackList(sort, order, statut),
    queryFn: () => apiClient.listFeedback(sort, order, statut === "tous" ? undefined : statut),
    // Le filtre change à chaque clic de la barre : sans cela, la file clignote
    // vers son squelette entre deux statuts déjà chargés.
    placeholderData: (precedent) => precedent,
  });
}

/**
 * Le nombre de signalements par statut (#500) — ce qui remplit « N nouveaux »
 * et le décompte de chaque filtre.
 *
 * Une requête à part, jamais un comptage sur la liste affichée : celle-ci est
 * filtrée, donc elle ne peut pas dire combien de lignes portent les trois
 * autres statuts.
 */
export function useFeedbackCounts() {
  return useQuery({
    queryKey: queryKeys.feedbackCounts(),
    queryFn: () => apiClient.countFeedback(),
  });
}

/**
 * Le détail complet d'un signalement, chargé **à l'ouverture** de sa modale.
 *
 * `enabled` plutôt qu'un appel au montage : même raison que `useGroup` — une
 * liste de signalements ne doit pas déclencher un détail par ligne pour un
 * geste que personne n'a demandé.
 */
export function useFeedback(id: number | null) {
  return useQuery({
    queryKey: queryKeys.feedback(id ?? 0),
    queryFn: () => apiClient.getFeedback(id as number),
    enabled: id !== null,
  });
}

/**
 * Change le statut d'un signalement. Périme la liste **et** le détail : la
 * liste affiche le statut de chaque ligne, le détail celui qu'on vient de
 * changer — les deux mentiraient sinon jusqu'au prochain montage.
 */
export function useUpdateFeedbackStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: Feedback["status"] }) =>
      apiClient.updateFeedbackStatus(id, { status }),
    onSuccess: (_donnees, { id }) => {
      qc.invalidateQueries({ queryKey: ["admin-feedback"] });
      qc.invalidateQueries({ queryKey: queryKeys.feedback(id) });
    },
  });
}

/** Enregistre l'URL de l'issue créée à la main — aucun appel à l'API GitHub. */
export function useUpdateFeedbackGithubUrl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, githubUrl }: { id: number; githubUrl: string }) =>
      apiClient.updateFeedbackGithubUrl(id, githubUrl),
    onSuccess: (_donnees, { id }) => {
      qc.invalidateQueries({ queryKey: ["admin-feedback"] });
      qc.invalidateQueries({ queryKey: queryKeys.feedback(id) });
    },
  });
}

// ── Journal d'administration (#501) ─────────────────────────────────────────

export const TAILLE_PAGE_JOURNAL = 20;

export function useAdminActionLog(page = 1) {
  return useQuery({
    queryKey: queryKeys.adminActionLog(page),
    queryFn: () => apiClient.getActionLog(page, TAILLE_PAGE_JOURNAL),
    placeholderData: (precedent) => precedent,
  });
}

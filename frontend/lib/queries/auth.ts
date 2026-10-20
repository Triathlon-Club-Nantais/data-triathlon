import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useHydrated } from "@/hooks/useHydrated";
import { ApiError, apiClient } from "@/lib/api/client";
import type { AuthMethod, SeasonGoalWrite, SessionUser } from "@/lib/types";
import { queryKeys } from "./keys";

/**
 * Signal de présence posé par le backend à la connexion (#427), lisible en JS
 * — contrairement au cookie de session, `HttpOnly` par nécessité. Son absence
 * ne garantit pas un vrai 401 (session expirée, révoquée), mais dispense de la
 * requête dans l'immense majorité des visites, qui sont anonymes.
 */
function visiteurProbablementConnecte(): boolean {
  if (typeof document === "undefined") return true;
  return document.cookie
    .split("; ")
    .some((cookie) => cookie.startsWith("tcn_logged_in="));
}

/** Au-delà, mieux vaut dire la panne que faire patienter en silence. */
const ATTENTE_MAX_429_S = 30;
const ESSAIS_MAX = 3;

function panneTransitoire(erreur: Error): boolean {
  if (!(erreur instanceof ApiError) || erreur.status === 0) return true; // coupure réseau
  if (erreur.status === 429) return (erreur.retryAfter ?? 0) <= ATTENTE_MAX_429_S;
  return erreur.status >= 500;
}

/**
 * Politique de la seule query session (#954), posée par `Providers` via
 * `setQueryDefaults` : une panne passagère de `/auth/me` (réveil à froid de
 * Render, 429 amont) ne doit pas faire passer un connecté pour un anonyme.
 * Les autres queries gardent leur `retry`. Le 401 n'arrive jamais ici,
 * `useSession` le traduit en `null`.
 */
export const SESSION_QUERY_DEFAULTS = {
  retry: (echecs: number, erreur: Error) => echecs < ESSAIS_MAX && panneTransitoire(erreur),
  retryDelay: (echecs: number, erreur: Error) =>
    erreur instanceof ApiError && erreur.status === 429 && erreur.retryAfter !== null
      ? erreur.retryAfter * 1000
      : Math.min(1000 * 2 ** echecs, 8000),
  // Un retour sur l'onglet répare une session illisible, sans relancer
  // `/auth/me` à chaque focus quand tout va bien.
  refetchOnWindowFocus: (query: { state: { status: string } }) => query.state.status === "error",
};

/**
 * Session courante, ou `null` si le visiteur est anonyme.
 *
 * Un 401 n'est **pas** une erreur ici : « pas connecté » est l'état par défaut
 * du site, qui reste intégralement public. Toute autre panne, elle, remonte,
 * après les essais de `SESSION_QUERY_DEFAULTS`.
 */
export function useSession() {
  return useQuery<SessionUser | null>({
    queryKey: queryKeys.session(),
    queryFn: async () => {
      if (!visiteurProbablementConnecte()) return null;
      try {
        return await apiClient.getSession();
      } catch (erreur) {
        if (erreur instanceof ApiError && erreur.status === 401) return null;
        throw erreur;
      }
    },
  });
}

/**
 * Moyens de connexion disponibles. Une liste vide est une réponse valide.
 *
 * `retry: false`, comme `useAdminPermissions` : une panne (backend endormi,
 * 500) doit lever `isError` immédiatement pour que `/login` l'affiche (#494),
 * pas après le délai des trois essais par défaut.
 */
export function useAuthMethods() {
  return useQuery<AuthMethod[]>({
    queryKey: queryKeys.authMethods(),
    queryFn: () => apiClient.listAuthMethods(),
    retry: false,
  });
}

/** Moyens de connexion liés au compte de la session (#1663). */
export function useMyIdentities() {
  return useQuery({
    queryKey: queryKeys.myIdentities(),
    queryFn: () => apiClient.getMyIdentities(),
    retry: false,
  });
}

/** Déconnexion de **cet** appareil seul (FR-014). */
export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.logout(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.session() }),
  });
}

/**
 * Rattachement à sa fiche (#1325) : chaque geste ne change que la session,
 * qui porte la fiche rattachée et la demande en cours.
 */
function useSessionMutation<T>(mutationFn: (arg: T) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.session() }),
  });
}

export function useRequestAthleteClaim() {
  return useSessionMutation((athleteId: number) => apiClient.requestAthleteClaim(athleteId));
}

export function useCancelAthleteClaim() {
  return useSessionMutation(() => apiClient.cancelAthleteClaim());
}

export function useDetachAthlete() {
  return useSessionMutation(() => apiClient.detachAthlete());
}

/** Mes réclamations de résultat (#1637) ; `enabled` faux sans fiche rattachée. */
export function useMyResultClaims(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.myResultClaims(),
    queryFn: () => apiClient.getMyResultClaims(),
    enabled,
    retry: false,
  });
}

/** Relais trouvés par nom d'équipe (#1739) ; `enabled` faux sous 3 caractères ou sans fiche. */
export function useMyTeamResults(q: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.myTeamResults(q),
    queryFn: () => apiClient.searchMyTeamResults(q),
    enabled,
    retry: false,
  });
}

function useResultClaimMutation<T>(mutationFn: (arg: T) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.myResultClaims() }),
  });
}

export function useRequestResultClaim() {
  return useResultClaimMutation(
    ({ participationId, kind = "result" }: { participationId: number; kind?: "result" | "team" }) =>
      apiClient.requestResultClaim(participationId, kind),
  );
}

export function useCancelResultClaim() {
  return useResultClaimMutation((claimId: number) => apiClient.cancelResultClaim(claimId));
}

/** Mes actions de bénévolat validées (#1696) ; liste vide sans fiche rattachée. */
export function useMyVolunteerActions(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.myVolunteerActions(),
    queryFn: () => apiClient.getMyVolunteerActions(),
    enabled,
    retry: false,
  });
}

/** Objectifs de saison du compte rattaché (#1373) ; `enabled` faux sans fiche. */
export function useSeasonGoals(enabled: boolean, season: number) {
  return useQuery({
    queryKey: queryKeys.seasonGoals(season),
    queryFn: () => apiClient.getSeasonGoals(season),
    enabled,
    retry: false,
  });
}

function useGoalMutation<T>(mutationFn: (arg: T) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.seasonGoals() }),
  });
}

export function useSaveSeasonGoal() {
  return useGoalMutation(({ id, body }: { id: number | null; body: SeasonGoalWrite }) =>
    id === null ? apiClient.createSeasonGoal(body) : apiClient.updateSeasonGoal(id, body),
  );
}

export function useDeleteSeasonGoal() {
  return useGoalMutation((id: number) => apiClient.deleteSeasonGoal(id));
}

/** Suppression du compte de la session, puis déconnexion (#1326). */
export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.deleteAccount(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.session() }),
  });
}

/**
 * `useSession`, sans session tant que le composant n'est pas hydraté (#1090).
 *
 * Le serveur n'a jamais la session. React Query rend pourtant le cache dès le
 * premier rendu client : quand `/auth/me` a répondu avant l'arrivée d'une page
 * streamée (fiche athlète, fiche épreuve), ce rendu différait du HTML serveur,
 * d'où l'erreur d'hydratation #418 et un second rendu complet de la frontière.
 * Tout composant d'un écran public rendu côté serveur lit la session par ici.
 */
export function useHydratedSession() {
  const session = useSession();
  const hydrate = useHydrated();
  return hydrate ? session : { ...session, data: undefined };
}

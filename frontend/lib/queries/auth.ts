import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiClient } from "@/lib/api/client";
import type { AuthMethod, SessionUser } from "@/lib/types";
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

/** Déconnexion de **cet** appareil seul (FR-014). */
export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.logout(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.session() }),
  });
}

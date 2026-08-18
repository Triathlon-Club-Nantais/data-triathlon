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

/**
 * Session courante, ou `null` si le visiteur est anonyme.
 *
 * Un 401 n'est **pas** une erreur ici : « pas connecté » est l'état par défaut
 * du site, qui reste intégralement public. Toute autre panne, elle, remonte.
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
    retry: false,
  });
}

/** Moyens de connexion disponibles. Une liste vide est une réponse valide. */
export function useAuthMethods() {
  return useQuery<AuthMethod[]>({
    queryKey: queryKeys.authMethods(),
    queryFn: () => apiClient.listAuthMethods(),
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

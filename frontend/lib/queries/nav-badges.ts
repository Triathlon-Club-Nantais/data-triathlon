"use client";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "./keys";

/**
 * Les pastilles du rail en un appel (#1385) : huit requêtes en rafale se
 * disputaient le seul process du backend avec les données de la page.
 *
 * `staleTime` de 5 min, le plus long des huit d'avant : deux comptes rejouent
 * une revue entière (#908, #1352). Une écriture la périme quand même : toute
 * mutation réussie l'invalide (`app/providers.tsx`).
 *
 * Hors de `./admin` : la nav est montée par le layout racine, et Turbopack y
 * embarquerait le module entier, sur toutes les pages (#1559).
 */
function useAdminBadgeCounts(actif = true) {
  return useQuery({
    queryKey: queryKeys.adminBadgeCounts(),
    queryFn: () => apiClient.getAdminBadgeCounts(),
    enabled: actif,
    staleTime: 5 * 60_000,
    // Une panne tait toutes les pastilles d'un coup : ne pas laisser « … » ~7 s.
    retry: 1,
  });
}

/**
 * Les compteurs annoncés par la navigation (#119, #726, #1385).
 *
 * `nav.config.ts` ne porte qu'une **clé** ; la réponse de
 * `GET /admin/badge-counts` est indexée par ces mêmes clés, et n'en porte que
 * ce que la session peut voir : le filtrage par pouvoir est au serveur. La nav
 * est montée sur toutes les pages, donc la requête ne part que pour un compte
 * d'administration ou d'encadrement (`canAdminister`), jamais pour un visiteur.
 *
 * `feedback` compte les retours `nouveau`, la file d'attente et non
 * l'historique (ADM-10). `quality` ne compte que les épreuves sans avis humain
 * (#1232). `validation` (« Validation des épreuves ») n'a pas de pouvoir RBAC :
 * le serveur la rend au porteur de `benevole_access:manage` ou du cookie
 * bénévoles, illisible côté client.
 */
export function useNavBadges(canAdminister: boolean): {
  counts: Record<string, number | undefined>;
  loading: boolean;
} {
  const badges = useAdminBadgeCounts(canAdminister);
  return {
    counts: badges.data ?? {},
    // Le premier chargement seul : un compte déjà connu se garde à l'écran
    // pendant qu'il se rafraîchit.
    loading: badges.isLoading,
  };
}

/**
 * Nom accessible du compteur d'une entrée (#119, #726) : un lecteur d'écran
 * annonçant juste le chiffre (« Revalidation qualité 4 ») ne dit pas ce qu'il
 * dénombre. Une clé par entrée du `switch`, sur le même patron que
 * `useNavBadges`. Partagé par le rail et le sommaire `/admin` (#1246).
 */
export function libelleCompteur(badge: string | undefined, n: number): string {
  switch (badge) {
    case "quality":
      return `${n} épreuve${n > 1 ? "s" : ""} à revalider`;
    case "duplicates":
      return `${n} doublon${n > 1 ? "s" : ""} suspect${n > 1 ? "s" : ""}`;
    case "providers":
      return `${n} fournisseur${n > 1 ? "s" : ""} en attente`;
    case "feedback":
      return `${n} nouveau${n > 1 ? "x" : ""} retour${n > 1 ? "s" : ""} utilisateur${n > 1 ? "s" : ""}`;
    case "identities":
      return `${n} cas d'identité à trancher`;
    case "members":
      return `${n} licencié${n > 1 ? "s" : ""} à rattacher`;
    case "volunteer":
      return `${n} déclaration${n > 1 ? "s" : ""} de bénévolat en attente`;
    case "validation":
      return `${n} résultat${n > 1 ? "s" : ""} à valider`;
    case "backoffice":
      return `${n} élément${n > 1 ? "s" : ""} à traiter`;
    default:
      return String(n);
  }
}

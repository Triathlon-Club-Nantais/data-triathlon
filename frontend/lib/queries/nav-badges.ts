"use client";
import { useQuery } from "@tanstack/react-query";
import { TO_HANDLE } from "@/components/layout/nav.config";
import { apiClient } from "@/lib/api/client";
import { motCompte, plural } from "@/lib/utils/format";
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
 * d'administration ou d'encadrement (`enabled`), jamais pour un visiteur.
 *
 * `feedback` compte les retours `nouveau`, la file d'attente et non
 * l'historique (ADM-10). `quality` ne compte que les épreuves sans avis humain
 * (#1232). `validation` (« Validation des épreuves ») n'a pas de pouvoir RBAC :
 * le serveur la rend au porteur de `benevole_access:manage` ou du cookie
 * bénévoles, illisible côté client.
 */
export function useNavBadges(enabled: boolean): {
  counts: Record<string, number | undefined>;
  loading: boolean;
} {
  const badges = useAdminBadgeCounts(enabled);
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
      return `${motCompte(n, "épreuve")} à revalider`;
    case "duplicates":
      return `${motCompte(n, "doublon")} ${plural(n, "suspect")}`;
    case "providers":
      return `${motCompte(n, "fournisseur")} en attente`;
    case "feedback":
      return `${n} ${plural(n, "nouveau", "nouveaux")} ${plural(n, "retour")} ${plural(n, "utilisateur")}`;
    case "identities":
      return `${n} cas d'identité à trancher`;
    case "members":
      return `${motCompte(n, "licencié")} à rattacher`;
    case "volunteer":
      return `${motCompte(n, "déclaration")} de bénévolat en attente`;
    case "validation":
      return `${motCompte(n, "résultat")} à valider`;
    case "backoffice":
      return `${motCompte(n, "élément")} à traiter`;
    default:
      return String(n);
  }
}

/** Total « À traiter » du back-office : la pastille du sommaire et de sa tuile d'accueil. */
export function totalATraiter(items: { group?: string; count?: number }[]): number | undefined {
  const connus = items.filter((i) => i.group === TO_HANDLE && i.count !== undefined);
  return connus.length > 0 ? connus.reduce((somme, i) => somme + (i.count ?? 0), 0) : undefined;
}

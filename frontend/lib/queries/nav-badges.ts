"use client";
import {
  useBenevoleQueueCount,
  useClubMembersToSettleCount,
  useCourseDuplicatesCount,
  useFeedbackCounts,
  useIdentityReviewCount,
  usePendingProvidersCount,
  usePendingVolunteerActionsCount,
  useQualityQueueCount,
} from "./admin";

/**
 * Les compteurs annoncés par la navigation (#119, #726).
 *
 * `nav.config.ts` ne porte qu'une **clé** — une table de configuration ne fait
 * pas de requête. La correspondance clé → requête vit ici, et chaque requête
 * n'est émise que si la session porte le pouvoir de l'écran : la nav est montée
 * sur toutes les pages, un comptage inconditionnel le ferait payer à chaque
 * visiteur, y compris anonyme.
 *
 * `feedback` compte `nouveau` et non `total` : c'est la file d'attente que la
 * pastille annonce, pas l'historique complet — même sens que la vue par défaut
 * de `FeedbackTable` (ADM-10). `quality` ne compte que les épreuves sans avis
 * humain (#1232) : celles déjà jugées douteuses n'attendent plus personne.
 *
 * `validation` (« Validation des épreuves ») n'a pas de pouvoir RBAC : sa garde
 * est le cookie du mot de passe bénévoles, illisible côté client. La requête
 * part donc pour un compte d'administration (`peutAdministrer`), le seul
 * susceptible de porter aussi ce cookie, et son 401 tait la pastille. Un
 * bénévole sans compte n'a pas de pastille : la demander à tout visiteur
 * ferait payer la nav à chacun.
 */
export function useNavBadges(
  pouvoirs: Set<string>,
  peutAdministrer: boolean,
): Record<string, number | undefined> {
  const qualite = useQualityQueueCount(pouvoirs.has("quality:override"));
  const doublons = useCourseDuplicatesCount(pouvoirs.has("courses:sources"));
  const fournisseurs = usePendingProvidersCount(pouvoirs.has("pending_providers:read"));
  const retours = useFeedbackCounts(pouvoirs.has("feedback:read"));
  const identites = useIdentityReviewCount(pouvoirs.has("athletes:write"));
  const licencies = useClubMembersToSettleCount(pouvoirs.has("club_members:manage"));
  const benevolat = usePendingVolunteerActionsCount(pouvoirs.has("athletes:volunteer_validate"));
  const validation = useBenevoleQueueCount(peutAdministrer);
  return {
    quality: qualite.data?.total,
    duplicates: doublons.data?.total,
    providers: fournisseurs.data?.total,
    feedback: retours.data?.nouveau,
    identities: identites.data?.total,
    members: licencies.data?.total,
    volunteer: benevolat.data?.total,
    validation: validation.data?.total,
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
    default:
      return String(n);
  }
}

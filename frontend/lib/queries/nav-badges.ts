"use client";
import {
  useAdminCoursesCount,
  useCourseDuplicatesCount,
  useFeedbackCounts,
  usePendingProvidersCount,
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
 * de `FeedbackTable` (ADM-10).
 */
export function useNavBadges(pouvoirs: Set<string>): Record<string, number | undefined> {
  const qualite = useAdminCoursesCount({ unreliable: true }, pouvoirs.has("quality:override"));
  const doublons = useCourseDuplicatesCount(pouvoirs.has("courses:sources"));
  const fournisseurs = usePendingProvidersCount(pouvoirs.has("pending_providers:read"));
  const retours = useFeedbackCounts(pouvoirs.has("feedback:read"));
  return {
    quality: qualite.data?.total,
    duplicates: doublons.data?.total,
    providers: fournisseurs.data?.total,
    feedback: retours.data?.nouveau,
  };
}

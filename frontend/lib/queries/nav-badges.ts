"use client";
import { useAdminCoursesCount } from "./admin";

/**
 * Les compteurs annoncés par la navigation (#119).
 *
 * `nav.config.ts` ne porte qu'une **clé** — une table de configuration ne fait
 * pas de requête. La correspondance clé → requête vit ici, et chaque requête
 * n'est émise que si la session porte le pouvoir de l'écran : la nav est montée
 * sur toutes les pages, un comptage inconditionnel le ferait payer à chaque
 * visiteur, y compris anonyme.
 *
 * Une seule clé est branchée pour l'instant. Brancher « Doublons » ou « Retours
 * utilisateurs » tiendra en une ligne ici plus une dans `nav.config.ts` — mais
 * ces écrans rendent aujourd'hui des listes complètes sans route de comptage,
 * et télécharger une liste pour en afficher la taille serait payer cher un
 * chiffre.
 */
export function useNavBadges(pouvoirs: Set<string>): Record<string, number | undefined> {
  const qualite = useAdminCoursesCount({ unreliable: true }, pouvoirs.has("quality:override"));
  return { quality: qualite.data?.total };
}

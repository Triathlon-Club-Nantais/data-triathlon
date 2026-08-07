import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api/client";
import { apiServer } from "@/lib/api/server";

/**
 * Garde d'accès aux écrans d'administration (FR-040).
 *
 * **D'interface seulement** : les ressources d'administration de l'API restent
 * ouvertes, conformément à FR-035 — protéger des routes relève de #115. Cette
 * garde évite d'exposer un écran inutilisable, elle ne protège aucune donnée.
 *
 * Un layout, et non un `middleware.ts` : un middleware ne peut constater que la
 * **présence** du cookie, jamais sa validité — il laisserait passer une session
 * révoquée ou expirée — et son `matcher`, mal borné, intercepterait `/api/*`,
 * cassant la réindirection vers le backend. Un layout couvre en outre les
 * futures sous-routes d'administration sans qu'on y pense.
 *
 * **Elle ne redirige que si une connexion est possible.** Deux cas où fermer
 * serait pire qu'ouvrir, et où l'on rend donc les enfants :
 *
 * - *aucun moyen de connexion* — sans les secrets `AUTH_*`, `/auth/me` rend 401
 *   pour tout le monde. Comme `render.yaml` les déclare `sync: false`, c'est
 *   l'état de tout déploiement tant qu'un opérateur ne les a pas posés :
 *   rediriger ferait de `/admin`, écran ouvert jusqu'ici, une impasse pour
 *   **tous**, ce que FR-036 proscrit ;
 * - *backend injoignable* — un démarrage à froid de Render (le dépôt embarque un
 *   cron `keep-warm` pour le combattre) ne doit pas remplacer l'écran par la
 *   page d'erreur globale. Avant cette garde, la page s'affichait et c'est le
 *   tableau client qui signalait la panne, en place.
 *
 * **Elle referme en revanche sur une session sans pouvoir.** Être connecté ne
 * suffit pas : le catalogue de #115 ne contient que des pouvoirs
 * d'administration, donc n'en porter aucun signifie n'avoir rien à faire ici.
 *
 * Contrepartie assumée : `/admin`, jusqu'ici prérendue statiquement, devient
 * dynamique. C'est l'effet recherché.
 */
/** Le backend n'a pas répondu : « anonyme » n'est pas établi pour autant. */
const INDISPONIBLE = Symbol("session indisponible");

/**
 * Le sentinelle, en journalisant d'abord ce qui a échoué.
 *
 * Les deux pannes appellent la même conduite — laisser passer plutôt que
 * transformer un incident en impasse — mais pas le même diagnostic : un 502 est
 * un backend injoignable (démarrage à froid de Render), un 5xx sur `/auth/me`
 * est **notre** route qui plante, et un échec sans statut est le réseau. Sans
 * cette trace, la garde se dégrade en silence et rien nulle part ne le dit.
 */
// Le type de retour est annoté : sans lui l'inférence élargit le sentinelle en
// `symbol`, et `!== INDISPONIBLE` ne restreint plus rien.
function panne(quoi: string): (erreur: unknown) => typeof INDISPONIBLE {
  return (erreur: unknown) => {
    const statut = erreur instanceof ApiError ? erreur.status : "sans réponse";
    console.error(`[admin] ${quoi} indisponible (${statut}) : ${erreur}`);
    return INDISPONIBLE;
  };
}

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const [session, methodes] = await Promise.all([
    apiServer.getSession().catch(panne("session")),
    apiServer.listAuthMethods().catch(panne("méthodes de connexion")),
  ]);

  // `=== null` et non `!session` : seul un 401 **avéré** dit que le visiteur est
  // anonyme. Une panne rend le sentinelle, et ne doit pas être lue comme un refus.
  if (session === null && methodes !== INDISPONIBLE && methodes.length > 0) {
    redirect("/login");
  }

  // Une session sans le moindre pouvoir n'a rien à administrer : **tout** code du
  // catalogue (#115) en est un — consulter des résultats n'en demande aucun. Vers
  // `/dashboard` et non `/login` : ce visiteur est connecté, l'y renvoyer serait
  // une boucle. La branche ne peut pas fermer un déploiement sans `AUTH_*` : sans
  // ces secrets, personne n'obtient de session et `session` vaut `null` (FR-036).
  if (session !== null && session !== INDISPONIBLE && session.permissions.length === 0) {
    redirect("/dashboard");
  }

  return <>{children}</>;
}

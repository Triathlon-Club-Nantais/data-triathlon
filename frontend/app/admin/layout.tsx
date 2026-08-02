import { redirect } from "next/navigation";
import type { ReactNode } from "react";
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
 * Contrepartie assumée : `/admin`, jusqu'ici prérendue statiquement, devient
 * dynamique. C'est l'effet recherché.
 */
/** Le backend n'a pas répondu : « anonyme » n'est pas établi pour autant. */
const INDISPONIBLE = Symbol("session indisponible");

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const [session, methodes] = await Promise.all([
    apiServer.getSession().catch(() => INDISPONIBLE),
    apiServer.listAuthMethods().catch(() => []),
  ]);

  // `=== null` et non `!session` : seul un 401 **avéré** dit que le visiteur est
  // anonyme. Une panne rend le sentinelle, et ne doit pas être lue comme un refus.
  if (session === null && methodes.length > 0) redirect("/login");
  return <>{children}</>;
}

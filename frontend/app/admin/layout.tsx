import { redirect } from "next/navigation";
import Link from "next/link";
import { BookOpen } from "lucide-react";
import type { ReactNode } from "react";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { NoAdminAccess } from "@/components/admin/NoAdminAccess";
import { PageShell } from "@/components/layout/PageShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ApiError } from "@/lib/api/client";
import { apiServer } from "@/lib/api/server";

/**
 * Garde d'accès aux écrans d'administration (FR-040).
 *
 * **D'interface seulement** : depuis #115, chaque route `/admin/*` de l'API est
 * gardée par `require_permission`, et c'est elle qui protège les données.
 * Cette garde évite seulement d'afficher un écran inutilisable.
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
 * **Elle referme en revanche sur une session sans pouvoir d'administration.**
 * Être connecté ne suffit pas, et `pages:preview` ne compte pas : c'est un
 * pouvoir de consultation, marqué comme tel dans le catalogue backend et lu ici
 * par `can_administer` (#1109). Elle ne redirige pas : le callback SSO mène
 * toujours à `/admin`, et une redirection muette faisait croire à une
 * connexion ratée. Elle rend `NoAdminAccess` à la place des enfants.
 *
 * **Elle ne vérifie pas le code d'accès au site.** La plupart des routes
 * `/admin/*` l'exigent en plus de la session (#509), mais `/admin/acces` doit
 * rester joignable sans lui pour poser le premier code. Un écran refusé pour
 * cette raison le dit lui-même : son 401 porte `code: "site_access_required"`,
 * que `messageDeRefus` distingue d'une session expirée (#877).
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

  // La branche ne peut pas fermer un déploiement sans `AUTH_*` : sans ces
  // secrets, personne n'obtient de session et `session` vaut `null` (FR-036).
  // Le lien « Guide » disparaît avec les enfants : il mène à des écrans fermés.
  if (session !== null && session !== INDISPONIBLE && !session.can_administer) {
    return (
      <PageShell>
        <div className="space-y-6">
          <PageHeader title="Back-office" />
          <NoAdminAccess />
        </div>
      </PageShell>
    );
  }

  // Le dialog des gestes destructifs, monté une fois pour toutes les
  // sous-routes (#499). Composant client sous un layout serveur : les enfants
  // rendus par le serveur traversent le provider sans devenir clients.
  return (
    <DangerConfirmProvider>
      {/* Lien fixe vers le guide (#865), hors de `nav.config.ts` par choix
          délibéré : voir le commentaire sur `a-flags` dans nav.config.ts et
          research.md. La garde ci-dessus (`can_administer`) suffit, aucun
          `permission` par écran n'est donc nécessaire ici. */}
      <div
        className="mx-auto flex justify-end px-4 pt-4 sm:px-8 md:px-10"
        style={{ maxWidth: "var(--tcn-content-max)" }}
      >
        <Link
          href="/admin/guide"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--tcn-text-faint)] transition-colors hover:text-foreground"
        >
          <BookOpen className="size-4" aria-hidden />
          Guide
        </Link>
      </div>
      {children}
    </DangerConfirmProvider>
  );
}

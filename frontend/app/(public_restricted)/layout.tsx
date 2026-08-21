import type { ReactNode } from "react";
import { SiteAccessGate } from "@/components/site-access/SiteAccessGate";
import { ApiError } from "@/lib/api/client";
import { apiServer } from "@/lib/api/server";

/**
 * Garde d'accès au site (#509) — ferme tout ce qui vit sous ce groupe de
 * routes derrière le mot de passe partagé aux adhérents.
 *
 * Un layout, et non `middleware.ts` : même raison que `admin/layout.tsx`
 * (route sœur, sa propre garde SSO/RBAC inchangée) — un middleware ne
 * constate que la présence du cookie, jamais sa validité, et son `matcher`
 * casse facilement les rewrites `/api/*`. Posé sur ce groupe et non sur
 * `app/layout.tsx` : `/acces`, `/benevoles` **et `/admin`** restent des
 * routes sœurs, jamais soumises à cette garde — `admin` en est sorti après
 * coup (revue finale de #509) pour ne pas fermer le seul chemin navigateur
 * permettant de poser le tout premier mot de passe (voir la spec de design).
 *
 * Conséquence assumée : toute page de ce groupe devient dynamique — c'est
 * l'effet recherché, au même titre que pour `/admin` avant elle.
 */
/** Le backend n'a pas répondu, ou a répondu autre chose que 200/401 : "invalide" n'est pas établi. */
const INDISPONIBLE = Symbol("accès site indisponible");

/**
 * Le sentinelle, en journalisant d'abord ce qui a échoué — même idiome que
 * `admin/layout.tsx` : la même conduite (laisser passer plutôt que fermer un
 * incident) mais un diagnostic différent selon le statut, sans quoi la garde
 * se dégraderait en silence.
 */
function panne(erreur: unknown): typeof INDISPONIBLE {
  const statut = erreur instanceof ApiError ? erreur.status : "sans réponse";
  console.error(`[site-access] session indisponible (${statut}) : ${erreur}`);
  return INDISPONIBLE;
}

export default async function ProtegeLayout({ children }: { children: ReactNode }) {
  const acces = await apiServer.checkSiteAccess().catch(panne);
  // `=== false` et non `!acces` : seul un 401 **avéré** dit que le cookie est
  // absent ou invalide. Une panne rend le sentinelle, et ne doit jamais être
  // lue comme un refus — cf. `admin/layout.tsx` pour le même raisonnement.
  //
  // Le formulaire est rendu **à la place** des enfants, et non par une
  // redirection vers `/acces` : un layout serveur ne reçoit ni le chemin
  // demandé ni les `searchParams` (Next 16), donc `redirect("/acces")` perdait
  // la destination — quelqu'un qui suivait un lien partagé vers `/courses/42`
  // saisissait le mot de passe et atterrissait sur le tableau de bord (relevé
  // en revue de #513). Sur place, l'URL ne bouge pas : le rafraîchissement qui
  // suit la connexion rejoue ce layout, cookie en main, et rend la page
  // demandée. Il n'y a plus de destination à transporter, donc pas de
  // paramètre `next` à valider contre la redirection ouverte — et toujours pas
  // de `middleware.ts`, seul autre endroit d'où le chemin serait lisible.
  //
  // `/acces` reste une route à part entière, cible d'une navigation directe et
  // point d'entrée après une déconnexion : c'est le même formulaire, avec
  // `apres="accueil"` puisqu'il n'y a là aucune page demandée à rejouer.
  if (acces === false) {
    return <SiteAccessGate />;
  }
  return <>{children}</>;
}

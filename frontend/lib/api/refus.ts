import { ApiError } from "@/lib/api/client";

/** `code` du 401 de la garde du site (`SiteAccessRequiredError`, backend). */
const SITE_ACCESS_REQUIRED = "site_access_required";

/** Même 401 que la session SSO, mais c'est le code du site qui manque (#877). */
export function estRefusDuSite(erreur: Error): boolean {
  return erreur instanceof ApiError && erreur.status === 401 && erreur.code === SITE_ACCESS_REQUIRED;
}

/**
 * Ce qu'un refus doit dire, et qu'une liste vide ne doit pas dire.
 *
 * Sur un 403, `data` est `undefined` : l'écran qui ne lit que `data` affiche son
 * état vide et **ment** — « aucun fournisseur signalé » (#115), « personne
 * n'est autorisé » (#170), « le club n'a aucun administrateur » (#239). Quatre
 * écrans en portaient chacun leur copie ; les faire diverger n'aurait tenu qu'à
 * un ajustement.
 *
 * Les deux mots restent à l'appelant, faute d'être déductibles l'un de l'autre :
 * `sujet` est le nom **masculin pluriel** de ce qui manque (« les groupes n'ont
 * pas pu être chargés »), `action` le geste refusé, qui n'est pas toujours une
 * consultation — la liste des accès se *gère*, elle ne se consulte pas.
 */
export function messageDeRefus(
  erreur: Error,
  { sujet, action }: { sujet: string; action: string },
): { title: string; description: string } {
  const statut = erreur instanceof ApiError ? erreur.status : 0;
  if (estRefusDuSite(erreur)) {
    return {
      title: "Code d'accès requis",
      description:
        "Le code d'accès au site manque ou a expiré. " +
        `Saisissez-le sur la page d'accès au site pour consulter les ${sujet}.`,
    };
  }
  if (statut === 401) {
    return {
      title: "Session expirée",
      description: `Reconnectez-vous pour consulter les ${sujet}.`,
    };
  }
  if (statut === 403) {
    return {
      title: "Accès refusé",
      description:
        `Votre rôle ne permet pas de ${action}. ` +
        "Demandez le pouvoir correspondant à un administrateur.",
    };
  }
  return {
    title: "Liste indisponible",
    description: `Les ${sujet} n'ont pas pu être chargés. Réessayez plus tard.`,
  };
}

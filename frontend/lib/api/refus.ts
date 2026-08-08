import { ApiError } from "@/lib/api/client";

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

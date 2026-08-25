"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "@/lib/api/client";
import {
  brouillonDepuis,
  erreurDeSaisie,
  estSale,
  LIBELLE_ETAPE,
  planEnregistrement,
  rebaser,
  type Brouillon,
  type Etape,
} from "@/lib/benevoles/brouillon";
import type { Participation } from "@/lib/types";

/**
 * L'état du formulaire unique du panneau bénévole (#490, PROF-10).
 *
 * Un seul brouillon, un seul `enregistrer()`, une seule zone d'erreur — contre
 * quatre gestes d'écriture indépendants jusqu'ici, dont aucun ne signalait
 * qu'on l'avait oublié avant de valider.
 */
export function useBrouillon(
  participationInitiale: Participation,
  { onChanged, onSessionExpired }: {
    onChanged: (p: Participation) => void;
    onSessionExpired?: () => void;
  },
) {
  // Base de comparaison pour `estSale`/`planEnregistrement` : le dernier état
  // **confirmé par le serveur**, pas la prop telle quelle. Un enregistrement
  // (même partiel) la met à jour localement dans le même geste que le
  // rebasage du brouillon, sans attendre le rendu suivant du parent — la prop
  // n'est pas garantie d'avoir rattrapé ce que ce hook vient lui-même
  // d'obtenir. Elle peut aussi être **en retard** pour une tout autre raison
  // (un rechargement d'arrière-plan du parent, `useFileValidation.charger()`,
  // qui refait `GET /benevoles/queue` sans changer l'id sélectionné donc sans
  // remonter ce hook) : l'effet ci-dessous la resynchronise sur cette base
  // quand la prop change pour une raison qui n'est pas notre propre
  // enregistrement — jamais le brouillon en cours, qui doit survivre intact à
  // un rechargement d'arrière-plan.
  const [participation, setParticipation] = useState(participationInitiale);
  const [brouillon, setBrouillon] = useState<Brouillon>(() => brouillonDepuis(participationInitiale));
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);
  // Distinct d'`enCours` : celui-ci reste vrai pendant tout `validerLeResultat`
  // (l'éventuel `enregistrer()` compris), `validationEnCours` ne l'est que
  // pendant l'appel de validation lui-même — le seul appel réseau du geste le
  // plus fréquent de l'écran, un brouillon propre (#490, revue de branche
  // finale : le bouton affichait « Enregistrement… » pour un appel qui ne
  // fait que valider).
  const [validationEnCours, setValidationEnCours] = useState(false);

  // La dernière participation que *ce hook* a lui-même posée comme base après
  // un enregistrement. Si la prop qui arrive est cette même référence — le
  // parent nous renvoie exactement ce qu'on lui a donné via `onChanged` — la
  // resynchronisation ci-dessous est un no-op sur des données déjà à jour,
  // jamais un écrasement par quelque chose de plus vieux.
  const derniereEnregistrementLocal = useRef<Participation | null>(null);

  useEffect(() => {
    if (participationInitiale === derniereEnregistrementLocal.current) return;
    setParticipation(participationInitiale);
  }, [participationInitiale]);

  const modifier = useCallback((patch: Partial<Brouillon>) => {
    setErreur(null);
    setBrouillon((courant) => ({ ...courant, ...patch }));
  }, []);

  /** Exécute une étape et rend la participation dans son état d'après. */
  async function executer(etape: Etape, courante: Participation): Promise<Participation> {
    switch (etape.type) {
      case "nom_epreuve": {
        const course = await apiClient.renameCourseBenevole(courante.course.id, etape.nom);
        return { ...courante, course };
      }
      case "champs":
        return apiClient.updateParticipationFieldsBenevole(courante.id, etape.champs);
      case "reattribution":
        return apiClient.reassignParticipationBenevole(courante.id, etape.athleteId);
    }
  }

  const enregistrer = useCallback(async (): Promise<boolean> => {
    setErreur(null);

    const invalide = erreurDeSaisie(brouillon);
    if (invalide) {
      setErreur(invalide);
      return false;
    }

    const plan = planEnregistrement(brouillon, participation);
    if (plan.length === 0) return true;

    setEnCours(true);
    let courante = participation;
    const reussies: Etape["type"][] = [];
    try {
      for (const etape of plan) {
        try {
          courante = await executer(etape, courante);
          reussies.push(etape.type);
        } catch (err) {
          // Une session expirée prévient le parent plutôt que d'afficher une
          // erreur générique sur un geste qui ne peut plus aboutir — sinon le
          // bénévole reste bloqué jusqu'au rechargement manuel (revue de #271).
          if (err instanceof ApiError && err.status === 401) {
            onSessionExpired?.();
            return false;
          }
          const detail = err instanceof ApiError ? err.message : "Réessayez plus tard.";
          setErreur(`${LIBELLE_ETAPE[etape.type]} : ${detail}`);
          return false;
        }
      }
      return true;
    } finally {
      setEnCours(false);
      // Ce qui est passé est commité côté serveur, même si la suite a échoué :
      // le brouillon et la base de comparaison se reposent dessus, le parent
      // apprend le nouvel état.
      if (reussies.length > 0) {
        setBrouillon((b) => rebaser(b, courante, reussies));
        derniereEnregistrementLocal.current = courante;
        setParticipation(courante);
        onChanged(courante);
      }
    }
  }, [brouillon, participation, onChanged, onSessionExpired]);

  const validerLeResultat = useCallback(async () => {
    if (!(await enregistrer())) return;
    setEnCours(true);
    setValidationEnCours(true);
    try {
      onChanged(await apiClient.validateParticipationBenevole(participation.id));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onSessionExpired?.();
        return;
      }
      setErreur(err instanceof ApiError ? err.message : "La validation a échoué. Réessayez plus tard.");
    } finally {
      setEnCours(false);
      setValidationEnCours(false);
    }
  }, [enregistrer, participation.id, onChanged, onSessionExpired]);

  return {
    brouillon,
    modifier,
    sale: estSale(brouillon, participation),
    erreur,
    enCours,
    validationEnCours,
    enregistrer,
    validerLeResultat,
  };
}

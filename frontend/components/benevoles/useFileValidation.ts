"use client";

import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiClient, ApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import { suivantApresRetrait } from "@/lib/benevoles/file";
import type { Participation } from "@/lib/types";

export type EtatFile = "chargement" | "gate" | "file" | "erreur";

/** Reste à traiter, dit en français plutôt qu'en nombre nu. */
function reste(nombre: number): string {
  if (nombre === 0) return "file vide.";
  return nombre === 1 ? "1 restant." : `${nombre} restants.`;
}

/**
 * La file de validation bénévole et son enchaînement (#490, PROF-9).
 *
 * Le point clé est `surChangement` : jusqu'à #490 il remettait `selectedId` à
 * `null` après chaque validation, ce qui obligeait à repointer l'entrée
 * suivante à la main — le geste le plus fréquent de l'écran était le plus
 * coûteux.
 */
export function useFileValidation() {
  const [etat, setEtat] = useState<EtatFile>("chargement");
  const [participations, setParticipations] = useState<Participation[]>([]);
  const [rejetees, setRejetees] = useState<Participation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [traitees, setTraitees] = useState(0);
  const [annonce, setAnnonce] = useState("");
  const [sessionNotice, setSessionNotice] = useState("");
  // La pastille « Validation des épreuves » de la nav (#1232) : la file vient
  // de changer de taille, ou le cookie qui la garde d'apparaître ou de partir.
  const queryClient = useQueryClient();
  const refreshBadge = useCallback(
    () => queryClient.invalidateQueries({ queryKey: queryKeys.benevoleQueueCount() }),
    [queryClient],
  );

  const charger = useCallback(async () => {
    setEtat("chargement");
    try {
      const [resultats, rejets] = await Promise.all([
        apiClient.getBenevoleQueue(),
        apiClient.getBenevoleRejected(),
      ]);
      setParticipations(resultats);
      setRejetees(rejets);
      setSessionNotice("");
      setEtat("file");
    } catch (err) {
      setEtat(err instanceof ApiError && err.status === 401 ? "gate" : "erreur");
    }
    refreshBadge();
  }, [refreshBadge]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    charger();
  }, [charger]);

  /** Retire l'entrée de la file, enchaîne sur la suivante, compte et annonce.
   *
   *  Lit `participations` dans la portée plutôt que via un updater : le toast
   *  est un effet de bord, et React peut rejouer un updater (StrictMode) —
   *  le bénévole verrait deux toasts pour une seule validation. */
  const retirerEtEnchainer = useCallback(
    (id: number, message: (restants: number) => string) => {
      const suivant = suivantApresRetrait(participations, id);
      const restants = participations.filter((p) => p.id !== id);
      setParticipations(restants);
      setSelectedId((courant) => (courant === id || courant === null ? suivant : courant));
      const texte = message(restants.length);
      toast.success(texte);
      setAnnonce(texte);
      setTraitees((n) => n + 1);
      refreshBadge();
    },
    [participations, refreshBadge],
  );

  const surChangement = useCallback(
    (maj: Participation) => {
      if (!maj.is_pending_validation) {
        setRejetees((liste) => liste.filter((p) => p.id !== maj.id));
        retirerEtEnchainer(maj.id, (restants) => `Résultat validé — ${reste(restants)}`);
        return;
      }
      if (maj.is_rejected) {
        setRejetees((liste) => [maj, ...liste.filter((p) => p.id !== maj.id)]);
        retirerEtEnchainer(
          maj.id,
          (restants) => `Résultat signalé non conforme — ${reste(restants)}`,
        );
        return;
      }
      // Rejet annulé : revient dans la file sans compter — ce n'est pas un
      // traitement, c'est son annulation.
      if (rejetees.some((p) => p.id === maj.id)) {
        setRejetees((liste) => liste.filter((p) => p.id !== maj.id));
        setParticipations((liste) => [maj, ...liste.filter((p) => p.id !== maj.id)]);
        refreshBadge();
        return;
      }
      // Simple enregistrement de champs : on rafraîchit sur place, sans
      // enchaîner ni compter.
      setParticipations((liste) => liste.map((p) => (p.id === maj.id ? maj : p)));
    },
    [rejetees, retirerEtEnchainer, refreshBadge],
  );

  const selectionnee =
    participations.find((p) => p.id === selectedId) ??
    rejetees.find((p) => p.id === selectedId) ??
    null;

  return {
    etat,
    participations,
    rejetees,
    selectedId,
    selectionnee,
    traitees,
    annonce,
    /** Annonce de session, montée dans tous les états de l'écran (#1232). */
    sessionNotice,
    charger,
    selectionner: setSelectedId,
    surChangement,
    /** Cookie expiré ou mot de passe changé pendant que l'écran était ouvert. */
    surSessionExpiree: useCallback(() => setEtat("gate"), []),
    onLoggedOut: useCallback(() => {
      setSessionNotice("Vous êtes déconnecté.");
      setEtat("gate");
      refreshBadge();
    }, [refreshBadge]),
  };
}

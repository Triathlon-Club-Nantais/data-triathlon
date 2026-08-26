"use client";

import { useEffect, useState } from "react";
import {
  ATHLETE_CHANGED_EVENT,
  ATHLETE_LOST_EVENT,
  OPEN_PICKER_EVENT,
  useSelectedAthlete,
} from "@/components/layout/AthletePicker";

/**
 * Invitation discrète à choisir son athlète, pour qui atterrit sur
 * `/dashboard` sans l'avoir encore fait (#588 — suite de #467/#502, dont la
 * récompense — la bande « Ma saison » — restait invisible à qui n'avait pas
 * fait le geste).
 *
 * Volontairement **hors** de `Card`/`Bande` : `MaSaison.tsx` documente le
 * coût vertical déjà tendu (155px sous `sm`) de ce format, qu'une invitation
 * permanente à tous les visiteurs — l'écrasante majorité, qui ne choisira
 * jamais — ne peut pas se permettre de rejouer. Une ligne de la hauteur d'un
 * lien, donc, et le même mécanisme d'ouverture de palette que l'état
 * « perdu » de `MaSaison` (`OPEN_PICKER_EVENT`).
 *
 * Pas de fermeture définitive : le problème que #588 corrige est justement
 * que personne ne fait ce geste faute de le voir récompensé — la re-fermer
 * durablement rouvrirait ce risque, pour un gain incertain.
 *
 * Deux pièges relevés en revue de code, à ne pas rouvrir séparément :
 * - **`hydrated` retarde le premier rendu réel.** `useSelectedAthlete()` vaut
 *   `null` aussi bien avant hydratation qu'après un choix réellement vide —
 *   deux cas que `MaSaison` distingue en ne rendant rien dans les deux
 *   (`!athlete` couvre les deux). Ici, `null` déclenche l'affichage : sans
 *   ce garde-fou, la ligne apparaîtrait un instant pour un visiteur qui a
 *   pourtant déjà choisi, le temps que l'hydratation relise le stock réel.
 * - **`ficheADisparu` évite le doublon avec l'état « perdu » de `MaSaison`.**
 *   Un 404 sur `getAthlete` y purge le stock (`clearAthlete()`) *et* garde la
 *   bande affichée (« Votre fiche a changé ») — sans ce second état, les deux
 *   invitations à choisir un athlète se superposeraient. `ATHLETE_LOST_EVENT`
 *   est émis juste après `ATHLETE_CHANGED_EVENT` (celui de `clearAthlete()`)
 *   : l'ordre d'écoute ci-dessous doit donc laisser le second écraser le
 *   premier, jamais l'inverse.
 */
export function InvitationAthlete() {
  const athlete = useSelectedAthlete();
  const [hydrated, setHydrated] = useState(false);
  const [ficheADisparu, setFicheADisparu] = useState(false);

  useEffect(() => {
    // Signale la fin d'hydratation, patron déjà en place dans `MaSaison.tsx`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHydrated(true);
    const surPerte = () => setFicheADisparu(true);
    // Un nouveau choix (y compris depuis la palette rouverte par `MaSaison`
    // en état « perdu ») lève la mise en veille — l'ancienne fiche disparue
    // ne concerne plus l'athlète désormais retenu.
    const surChangement = () => setFicheADisparu(false);
    window.addEventListener(ATHLETE_LOST_EVENT, surPerte);
    window.addEventListener(ATHLETE_CHANGED_EVENT, surChangement);
    return () => {
      window.removeEventListener(ATHLETE_LOST_EVENT, surPerte);
      window.removeEventListener(ATHLETE_CHANGED_EVENT, surChangement);
    };
  }, []);

  if (!hydrated || athlete || ficheADisparu) return null;

  return (
    <div className="mb-4">
      <button
        type="button"
        onClick={() => window.dispatchEvent(new Event(OPEN_PICKER_EVENT))}
        className="text-sm font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
      >
        Retrouvez vos épreuves et vos podiums en tête de cet écran →
      </button>
    </div>
  );
}

"use client";

import { OPEN_PICKER_EVENT, useSelectedAthlete } from "@/components/layout/AthletePicker";

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
 */
export function InvitationAthlete() {
  const athlete = useSelectedAthlete();
  if (athlete) return null;

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

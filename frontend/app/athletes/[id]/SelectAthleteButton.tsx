"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/tcn";
import { clearAthlete, ATHLETE_CHANGED_EVENT, readAthlete, writeAthlete, type PickedAthlete } from "@/components/layout/AthletePicker";

/**
 * Choisir/relâcher l'athlète affiché comme athlète retenu, depuis sa
 * page profil (issue #323). `AppNav` reste la seule source de vérité côté
 * navigation — ce bouton se contente de lire/écrire le même stock et de
 * suivre le même événement de synchronisation.
 *
 * État initial neutre puis alignement en effet : le rendu serveur ne connaît
 * pas le `localStorage` (même patron d'hydratation que `AppNav.tsx`).
 */
export function SelectAthleteButton({ athlete }: { athlete: PickedAthlete }) {
  const [retenu, setRetenu] = useState(false);

  useEffect(() => {
    const aligner = () => setRetenu(readAthlete()?.id === athlete.id);
    aligner();
    window.addEventListener(ATHLETE_CHANGED_EVENT, aligner);
    return () => window.removeEventListener(ATHLETE_CHANGED_EVENT, aligner);
  }, [athlete.id]);

  // Même verbe que l'autre point d'entrée vers cette action (`AthletePicker`
  // aria-label « Choisir {nom} ») — la revue UI/UX a relevé la divergence
  // avec « Sélectionner »/« Relâcher » (issue #323). L'objet de l'action
  // reste nommé même sur l'état retenu, pour un lecteur d'écran qui saute
  // directement au bouton.
  return retenu ? (
    <Button variant="secondary" onClick={() => clearAthlete()}>
      Ne plus choisir cet athlète
    </Button>
  ) : (
    <Button variant="secondary" onClick={() => writeAthlete(athlete)}>
      Choisir cet athlète
    </Button>
  );
}

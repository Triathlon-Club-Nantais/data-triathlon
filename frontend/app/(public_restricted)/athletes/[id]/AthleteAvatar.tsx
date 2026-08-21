"use client";

import { Avatar } from "@/components/tcn";
import { useIsSelectedAthlete } from "@/components/layout/AthletePicker";

/**
 * Avatar de l'en-tête du profil, cerclé d'orange quand ce profil **est**
 * l'athlète retenu (#467) : l'état ne se déduisait jusqu'ici que du libellé du
 * bouton, qui est une commande, pas un état affiché.
 *
 * L'anneau est un renfort décoratif — c'est la pastille « C'est vous » d'à côté
 * qui porte l'information pour un lecteur d'écran, l'`Avatar` étant
 * `aria-hidden` par construction. D'où l'état posé en `data-selected` et peint
 * en CSS (`.tcn-avatar-frame`) plutôt qu'annoncé.
 */
export function AthleteAvatar({ athleteId, name }: { athleteId: number; name: string }) {
  const retenu = useIsSelectedAthlete(athleteId);
  return (
    <span data-testid="athlete-avatar" data-selected={retenu} className="tcn-avatar-frame">
      <Avatar name={name} size={72} />
    </span>
  );
}

import type { Participation } from "@/lib/types";

/**
 * Résultat de relais : drapeau du résultat **ou** de l'épreuve, la même règle
 * que le serveur (`set_teammates`, podiums individuels). Une épreuve peut être
 * marquée relais à la main sans que ses résultats le soient.
 */
export function estRelais(participation: Participation): boolean {
  return participation.is_relay || participation.course.is_relay;
}

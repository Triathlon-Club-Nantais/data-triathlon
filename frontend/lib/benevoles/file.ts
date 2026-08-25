import type { Participation } from "@/lib/types";

/**
 * L'entrée à sélectionner après en avoir retiré une (#490, PROF-9).
 *
 * Celle qui prend la place libérée, à défaut la précédente, à défaut rien —
 * de sorte que `selectedId === null` avec une file non vide devienne un état
 * impossible, et que le bénévole n'ait plus à repointer à la main après chaque
 * validation.
 */
export function suivantApresRetrait(liste: Participation[], idRetire: number): number | null {
  const index = liste.findIndex((p) => p.id === idRetire);
  if (index === -1) return null;
  const restants = liste.filter((p) => p.id !== idRetire);
  if (restants.length === 0) return null;
  return (restants[index] ?? restants[restants.length - 1]).id;
}

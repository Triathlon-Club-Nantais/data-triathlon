/** Position (1-indexée) d'un id dans une liste déjà ordonnée, `null` s'il en est absent. */
export function trouverRang(id: number, ids: number[]): number | null {
  const index = ids.indexOf(id);
  return index === -1 ? null : index + 1;
}

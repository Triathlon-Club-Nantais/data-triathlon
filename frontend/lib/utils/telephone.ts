const TELEPHONE_FR = /(?<![\d+])(?:\+33\s?|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)/;

/**
 * Le premier numéro français d'un texte libre (« Parent X 06 00 00 00 00 »),
 * avec sa position pour le rendre cliquable sur place et le lien `tel:`.
 */
export function trouverTelephone(
  texte: string,
): { debut: number; fin: number; href: string } | null {
  const trouve = TELEPHONE_FR.exec(texte);
  if (!trouve) return null;
  return {
    debut: trouve.index,
    fin: trouve.index + trouve[0].length,
    href: `tel:${trouve[0].replace(/[^\d+]/g, "")}`,
  };
}

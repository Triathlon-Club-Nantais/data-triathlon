/**
 * Case and accent insensitive key (« Élodie » → « elodie »), like the server side
 * search (`deaccent` then SQL `lower`, #357). NFD splits each accent from its
 * letter, then the combining diacritical marks block (U+0300 to U+036F) is
 * dropped. Ligatures (œ, æ) are not decomposed by NFD and stay as they are.
 */
export function foldAccents(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

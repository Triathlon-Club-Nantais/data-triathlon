/**
 * Une `source_url` ne devient un lien cliquable que si c'est une URL `http(s)`.
 *
 * Le backend n'accepte qu'une URL commençant par « http » (et la création
 * manuelle n'en valide aucune) : on garde donc une défense en profondeur côté
 * UI pour n'ouvrir que des schémas web attendus et écarter tout `javascript:`,
 * `data:` ou schéma exotique.
 */
export function isHttpUrl(value: string | null | undefined): boolean {
  if (!value) return false;
  try {
    const { protocol } = new URL(value);
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}

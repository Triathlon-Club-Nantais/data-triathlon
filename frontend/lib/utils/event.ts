/** Nom d'épreuve affiché, suffixé « (Relais) » quand la course est un relais. */
export function formatEventName(name: string, isRelay: boolean): string {
  return isRelay ? `${name} (Relais)` : name;
}

/** Le compte rendu d'une opposition (#334), le même depuis la fiche et depuis l'écran des oppositions. */
export function messageApplique(anonymises: number): string {
  if (anonymises === 0) return "Opposition enregistrée : aucun résultat à ce nom pour l'instant.";
  return `Opposition appliquée : ${anonymises} résultat${anonymises > 1 ? "s" : ""} anonymisé${anonymises > 1 ? "s" : ""}.`;
}

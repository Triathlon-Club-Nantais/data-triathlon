import { motCompte, plural } from "@/lib/utils/format";

/** Le compte rendu d'une opposition (#334), le même depuis la fiche et depuis l'écran des oppositions. */
export function messageApplique(anonymises: number): string {
  if (anonymises === 0) return "Opposition enregistrée : aucun résultat à ce nom pour l'instant.";
  return `Opposition appliquée : ${motCompte(anonymises, "résultat")} ${plural(anonymises, "anonymisé")}.`;
}

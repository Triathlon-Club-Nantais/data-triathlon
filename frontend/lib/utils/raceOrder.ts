const NON_FINISHER = new Set(["DNF", "DNS", "DSQ"]);

/** Vrai si le statut est un non-finisher porteur de sigle (DNF/DNS/DSQ). */
export function isNonFinisher(status: string | null | undefined): boolean {
  return NON_FINISHER.has((status ?? "").toUpperCase());
}

// `orderParticipations`, `countOutcomes` et `isFinisher` ont été retirés avec la
// pagination du classement (#163). Les deux premiers prenaient le classement
// **entier** en argument ; appelés sur une tranche de vingt lignes, ils
// trieraient dans le vide et annonceraient « 20 partants » — sans erreur, ce qui
// est le pire des cas. L'ordre est désormais une propriété de la requête
// (`participation_repository`), les décomptes viennent de la synthèse d'épreuve.

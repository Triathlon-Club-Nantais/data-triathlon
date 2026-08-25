// Libellés complets des codes de catégorie (#486, RES-11).
//
// « S2, V1, V3, PoM, CA, JU » ne sont expliqués nulle part : un parent qui consulte le
// résultat de son enfant ne sait pas ce que « PoM » désigne.
//
// Côté écran et non en base : c'est un libellé d'affichage, il ne conditionne aucune
// requête, et le mettre en base ferait une migration pour une constante.
//
// La table est **bornée aux codes réellement rencontrés**, relevés sur la base de dev :
// 123 codes distincts relevant d'au moins trois nomenclatures. Une table plate ne les
// couvre pas — d'où les trois règles de dérivation ci-dessous, qui portent l'essentiel.
// Relevé complet : `specs/20260825-114345-page-epreuve-syntheses/releve-donnees.md`.

/** Codes de base de la nomenclature fédérale. */
const BASE: Record<string, string> = {
  PO: "Poussin",
  PU: "Pupille",
  BE: "Benjamin",
  MI: "Minime",
  CA: "Cadet",
  JU: "Junior",
  ES: "Espoir",
  SE: "Senior",
  S1: "Senior 1",
  S2: "Senior 2",
  S3: "Senior 3",
  S4: "Senior 4",
  V1: "Vétéran 1",
  V2: "Vétéran 2",
  V3: "Vétéran 3",
  V4: "Vétéran 4",
  V5: "Vétéran 5",
  V6: "Vétéran 6",
  V7: "Vétéran 7",
};

/** Séries « masters », étrangères à la nomenclature fédérale mais fréquentes. */
const MASTERS: Record<string, string> = {
  M0: "Master 0",
  M1: "Master 1",
  M2: "Master 2",
  M3: "Master 3",
  M4: "Master 4",
  M5: "Master 5",
  M6: "Master 6",
  MA1: "Master 1",
  MA2: "Master 2",
  MA3: "Master 3",
  MA4: "Master 4",
  MA5: "Master 5",
};

/** Équipes et relais, où le code ne désigne pas une classe d'âge. */
const EQUIPES: Record<string, string> = {
  REM: "Relais masculin",
  REF: "Relais féminin",
  REX: "Relais mixte",
  EQM: "Équipe masculine",
  EQF: "Équipe féminine",
  EQX: "Équipe mixte",
  MPM: "Relais par équipe",
};

// Trois lettres pour deux genres : les chronométreurs n'ont pas de convention commune.
const GENRES: Record<string, string> = { M: "hommes", H: "hommes", F: "femmes", D: "dames" };

/** Mot de genre en préfixe — « M SENIOR », « F VETERAN ». */
const GENRES_MOT: Record<string, string> = { M: "hommes", H: "hommes", F: "femmes" };

const MOTS: Record<string, string> = {
  POUSSIN: "Poussin",
  PUPILLE: "Pupille",
  BENJAMIN: "Benjamin",
  MINIME: "Minime",
  CADET: "Cadet",
  JUNIOR: "Junior",
  ESPOIR: "Espoir",
  SENIOR: "Senior",
  VETERAN: "Vétéran",
  MASTER: "Master",
};

function sansAccent(valeur: string): string {
  return valeur.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

/**
 * Libellé complet d'un code de catégorie, ou `null` si la table ne le connaît pas.
 *
 * `null` plutôt qu'un libellé inventé : sur 123 codes relevés, une queue de 37 codes à
 * 150 lignes n'a aucune correspondance sûre. L'appelant rend alors le code tel quel —
 * même réflexe que `describeQualityIssues`, qui laisse passer un code d'anomalie inconnu
 * avec son compteur plutôt que de l'avaler.
 */
export function categoryLabel(code: string | null | undefined): string | null {
  const brut = (code ?? "").trim();
  if (!brut || brut === "-") return null;

  const majuscules = sansAccent(brut).toUpperCase();

  const direct = BASE[majuscules] ?? MASTERS[majuscules] ?? EQUIPES[majuscules];
  if (direct) return direct;

  // « S2M », « V3H », « CaF » — le genre est accolé au code de base.
  const suffixe = majuscules.match(/^([A-Z]{1,2}\d?)([MHFD])$/);
  if (suffixe) {
    const racine = BASE[suffixe[1]] ?? MASTERS[suffixe[1]];
    if (racine) return `${racine}, ${GENRES[suffixe[2]]}`;
  }

  // « M SENIOR », « F VETERAN » — le genre est un mot, en préfixe.
  const prefixe = majuscules.match(/^([MHF])\s+([A-Z]+)$/);
  if (prefixe) {
    const classe = MOTS[prefixe[2]];
    if (classe) return `${classe}, ${GENRES_MOT[prefixe[1]]}`;
  }

  return null;
}

/**
 * Ce qu'on annonce pour un code : son libellé si on le connaît, le code sinon.
 *
 * Sert d'`aria-label` et d'infobulle. Le code seul reste affiché à l'œil — c'est la clé
 * de lecture du tableau, et la remplacer par « Vétéran 2 » élargirait la colonne sans
 * rien apprendre à qui connaît déjà la nomenclature.
 */
export function categoryTitle(code: string | null | undefined): string {
  const brut = (code ?? "").trim();
  const libelle = categoryLabel(brut);
  return libelle ? `${brut} — ${libelle}` : brut;
}

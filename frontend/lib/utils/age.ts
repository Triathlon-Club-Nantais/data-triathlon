/**
 * Âge en années révolues, calculé à l'affichage — jamais stocké (#867,
 * data-model.md §Validation : « l'âge se calcule à l'affichage »).
 *
 * `null` pour une date de naissance absente (profil pas encore renseigné) :
 * l'écran doit le dire plutôt qu'afficher un âge faux (spec.md, edge case).
 */
export function calculerAge(birthDate: string | null | undefined): number | null {
  if (!birthDate) return null;
  const match = String(birthDate).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  const naissance = new Date(+match[1], +match[2] - 1, +match[3]);
  if (Number.isNaN(naissance.getTime())) return null;
  const aujourdhui = new Date();
  let age = aujourdhui.getFullYear() - naissance.getFullYear();
  const pasEncoreAnniversaire =
    aujourdhui.getMonth() < naissance.getMonth() ||
    (aujourdhui.getMonth() === naissance.getMonth() &&
      aujourdhui.getDate() < naissance.getDate());
  if (pasEncoreAnniversaire) age -= 1;
  return age;
}

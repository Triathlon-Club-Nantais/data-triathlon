const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

/** « Ce week-end » jusqu'à 7 jours après la dernière course, sinon sa date. */
export function titreSortie(endDate: string, today: Date): string {
  const [annee, mois, jour] = endDate.split("-").map(Number);
  const fin = new Date(annee, mois - 1, jour);
  const jours = Math.floor((today.getTime() - fin.getTime()) / 86_400_000);
  return jours < 7 ? "Ce week-end" : `Dernière sortie · ${jour} ${MOIS_COURTS[mois - 1]}`;
}

/** Les douze mois de la saison `season` (septembre à août), à zéro quand vides. */
export function moisDeSaison(byMonth: Record<string, number>, season: number) {
  return Array.from({ length: 12 }, (_, i) => {
    const annee = season + Math.floor((8 + i) / 12);
    const index = (8 + i) % 12;
    const mois = `${annee}-${String(index + 1).padStart(2, "0")}`;
    return { mois, libelle: MOIS_COURTS[index], valeur: byMonth[mois] ?? 0 };
  });
}

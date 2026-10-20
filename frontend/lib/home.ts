import { currentSeason, seasonOf } from "@/lib/utils/season";

const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

function joursDepuis(endDate: string, today: Date): number {
  const [annee, mois, jour] = endDate.split("-").map(Number);
  return Math.floor((today.getTime() - new Date(annee, mois - 1, jour).getTime()) / 86_400_000);
}

/** Vrai quand la sortie s'est terminée il y a 0 à 2 jours (le point qui pulse). */
export function estToutRecent(endDate: string, today: Date): boolean {
  const jours = joursDepuis(endDate, today);
  return jours >= 0 && jours <= 2;
}

/** « Ce week-end » jusqu'à 7 jours après la dernière course, sinon sa date. */
export function titreSortie(endDate: string, today: Date): string {
  const [annee, mois, jour] = endDate.split("-").map(Number);
  if (joursDepuis(endDate, today) < 7) return "Ce week-end";
  const date = `${jour} ${MOIS_COURTS[mois - 1]}`;
  return `Dernière sortie · ${seasonOf(endDate) === currentSeason(today) ? date : `${date} ${annee}`}`;
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

/** Les mois de septembre à août des trois saisons les plus récentes de la sélection, côte à côte. */
export function moisComparesParSaison(byMonth: Record<string, number>, seasons: number[]) {
  const saisons = [...seasons].sort((a, b) => a - b).slice(-3);
  const parSaison = saisons.map((saison) => moisDeSaison(byMonth, saison));
  return {
    saisons,
    tronque: seasons.length > 3,
    mois: Array.from({ length: 12 }, (_, index) => ({
      index,
      libelle: parSaison[0][index].libelle,
      valeurs: parSaison.map((mois) => mois[index].valeur),
    })),
  };
}

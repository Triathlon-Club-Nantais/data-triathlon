import { eventTypeLabel } from "@/lib/constants";
import type { SeasonGoal } from "@/lib/types";
import { formatDate, localToday } from "@/lib/utils/date";

export function libelle(goal: SeasonGoal): string {
  const format = goal.event_type ? eventTypeLabel(goal.event_type) : null;
  if (goal.kind === "race") return `${goal.race_name}, ${formatDate(goal.race_date)}`;
  const target = goal.target ?? 0;
  if (goal.kind === "time") return `${format} en moins de ${hms(target)}`;
  const epreuves = `${target} ${target > 1 ? "épreuves" : "épreuve"}`;
  return format ? `${epreuves} de ${format}` : epreuves;
}

export function progression(goal: SeasonGoal): string {
  if (goal.kind === "race") return progressionEpreuve(goal);
  if (goal.kind === "time") return goal.best_time ? `Meilleur temps : ${goal.best_time}` : "Aucun temps sur la saison";
  return `${goal.count ?? 0} sur ${goal.target}`;
}

function progressionEpreuve(goal: SeasonGoal): string {
  switch (goal.outcome) {
    case "upcoming": {
      const jours = joursAvant(goal);
      return jours <= 0 ? "Aujourd'hui" : `Dans ${jours} ${jours > 1 ? "jours" : "jour"}`;
    }
    case "awaiting_results": return "En attente des résultats";
    case "reached": return goal.best_time ? `Temps : ${goal.best_time}` : "Résultat validé";
    case "missed": return goal.best_time ? `Temps : ${goal.best_time}` : "Aucun résultat validé";
  }
}

export function joursAvant(goal: SeasonGoal): number {
  return Math.round((Date.parse(goal.race_date ?? "") - Date.parse(localToday())) / 86_400_000);
}

export function hms(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

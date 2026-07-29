// Libellés utilisateur des anomalies de fiabilité d'une course.
// Codes canoniques : voir backend/app/services/quality.py — miroir strict.

/**
 * Rend `quality_issues` (dict {code: count}) en phrases françaises lisibles.
 * Un code inconnu est rendu tel quel avec son compteur, plutôt qu'ignoré :
 * un nouveau code côté backend restera visible en attendant la traduction.
 */
export function describeQualityIssues(issues: Record<string, number> | null | undefined): string[] {
  if (!issues) return [];
  return Object.entries(issues).map(([code, count]) => describeIssue(code, count));
}

function describeIssue(code: string, count: number): string {
  switch (code) {
    case "duplicate_bib":
      return `${count} ${plural(count, "dossard")} en doublon dans les données du chronométreur`;
    case "rank_gap":
      return `${count} ${plural(count, "trou")} dans le classement`;
    case "duplicate_rank":
      return `${count} ${plural(count, "rang")} partagé${plural(count, "", "s")} par plusieurs finishers`;
    case "finisher_without_time":
      return `${count} finisher${plural(count, "", "s")} sans temps`;
    case "unknown_status":
      return `${count} statut${plural(count, "", "s")} hors nomenclature`;
    case "no_participation":
      return "Course importée sans participation";
    default:
      return `${code}: ${count}`;
  }
}

function plural(count: number, singular: string, pluralForm?: string): string {
  return count > 1 ? (pluralForm ?? `${singular}s`) : singular;
}

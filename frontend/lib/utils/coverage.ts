export interface MonthCoverage {
  month: string; // "YYYY-MM"
  count: number;
}

interface DatedEvent {
  event_date: string | null;
}

/**
 * Décompte mensuel des épreuves, avec les mois sans épreuve comptés à zéro
 * plutôt qu'omis — un mois absent d'une `Map` ne se distingue pas d'un mois
 * jamais interrogé, un mois à `count: 0` si (#466, US11).
 */
export function monthlyCoverage(events: DatedEvent[]): MonthCoverage[] {
  const counts = new Map<string, number>();
  for (const { event_date } of events) {
    if (!event_date) continue;
    const month = event_date.slice(0, 7);
    counts.set(month, (counts.get(month) ?? 0) + 1);
  }

  const months = [...counts.keys()].sort();
  if (months.length === 0) return [];

  const [startYear, startMonth] = months[0].split("-").map(Number);
  const [endYear, endMonth] = months[months.length - 1].split("-").map(Number);

  const result: MonthCoverage[] = [];
  let year = startYear;
  let month = startMonth;
  while (year < endYear || (year === endYear && month <= endMonth)) {
    const key = `${year}-${String(month).padStart(2, "0")}`;
    result.push({ month: key, count: counts.get(key) ?? 0 });
    month += 1;
    if (month > 12) {
      month = 1;
      year += 1;
    }
  }
  return result;
}

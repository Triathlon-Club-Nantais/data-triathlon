import { formatMonthShort, formatMonth } from "@/lib/utils/date";

/**
 * Histogramme vertical de l'activité par mois (12 derniers mois présents).
 * Server-compatible (pas de dépendance graphique externe).
 */
export function MonthlyTrend({ byMonth }: { byMonth: Record<string, number> }) {
  const entries = Object.entries(byMonth)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-12);

  if (entries.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Pas encore de données mensuelles.
      </p>
    );
  }

  const max = Math.max(1, ...entries.map(([, v]) => v));

  return (
    <div className="flex h-44 items-end gap-1.5">
      {entries.map(([key, value]) => (
        <div
          key={key}
          className="group flex flex-1 flex-col items-center justify-end gap-1.5"
          title={`${formatMonth(key)} — ${value}`}
        >
          <span className="num text-[11px] font-bold text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
            {value}
          </span>
          <div
            className="w-full rounded-t-sm bg-[color-mix(in_oklch,var(--primary)_70%,transparent)] transition-[height] duration-500 group-hover:bg-primary"
            style={{ height: `${Math.max(4, (value / max) * 100)}%` }}
          />
          <span className="micro-label text-[8px] text-muted-foreground">
            {formatMonthShort(key)}
          </span>
        </div>
      ))}
    </div>
  );
}

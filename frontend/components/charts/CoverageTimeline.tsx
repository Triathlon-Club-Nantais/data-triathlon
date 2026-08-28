import { scaleLinear } from "d3-scale";
import { formatMonthShort } from "@/lib/utils/date";
import type { MonthCoverage } from "@/lib/utils/coverage";

/**
 * Vue d'ensemble mensuelle des épreuves couvertes, mois vides compris — à la
 * différence de `MonthlyTrend` (12 derniers mois glissants), cette vue porte
 * l'historique complet pour que les trous restent visibles (#466, US11).
 * Défilement horizontal propre : l'historique peut dépasser plusieurs années.
 */
export function CoverageTimeline({ months }: { months: MonthCoverage[] }) {
  if (months.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-[var(--tcn-text-faint)]">
        Pas encore de données de couverture.
      </p>
    );
  }

  const max = Math.max(1, ...months.map((m) => m.count));
  const heightScale = scaleLinear().domain([0, max]).range([0, 100]);

  // L'année n'est écrite que sur le premier mois et à chaque changement
  // d'année — jamais sur chaque libellé — même patron que `MonthlyTrend`
  // (#650) : l'historique complet porté ici dépasse plus souvent une année
  // civile que la fenêtre glissante de 12 mois de `MonthlyTrend`, ce qui
  // rendait deux barres (ex. janv 2025 et janv 2026) indiscernables (#700).
  const spansMultipleYears = new Set(months.map((m) => m.month.slice(0, 4))).size > 1;
  const withYearFlags = months.map((m, index) => {
    const year = m.month.slice(0, 4);
    const previousYear = index > 0 ? months[index - 1].month.slice(0, 4) : null;
    return spansMultipleYears && year !== previousYear;
  });
  const labels = months.map((m, index) =>
    formatMonthShort(m.month, { withYear: withYearFlags[index] }),
  );

  const gapLabels = months.flatMap((m, index) => (m.count === 0 ? [labels[index]] : []));
  const summary =
    months.map((m, index) => `${labels[index]} ${m.count}`).join(", ") +
    (gapLabels.length > 0
      ? `. ${gapLabels.length} mois sans épreuve : ${gapLabels.join(", ")}.`
      : ".");

  return (
    <div className="overflow-x-auto">
      <div
        role="img"
        aria-label={`Couverture mensuelle des épreuves : ${summary}`}
        className="flex h-40 items-end gap-1.5"
        style={{ minWidth: `${months.length * 28}px` }}
      >
        {months.map((m, index) => (
          <div key={m.month} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1.5">
            <span
              aria-hidden
              className="num whitespace-nowrap text-[11px] font-bold text-[var(--tcn-text-faint)]"
            >
              {m.count > 0 ? m.count : "—"}
            </span>
            <div
              className={
                m.count > 0
                  ? "w-full rounded-t-sm bg-[color-mix(in_oklch,var(--primary)_70%,transparent)]"
                  : "w-full rounded-t-sm border border-dashed border-[var(--tcn-border)]"
              }
              style={{ height: `${m.count > 0 ? Math.max(4, heightScale(m.count)) : 4}%` }}
            />
            <span
              aria-hidden
              className="micro-label whitespace-nowrap text-[var(--tcn-text-faint)]"
            >
              {labels[index]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

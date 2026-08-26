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

  const gaps = months.filter((m) => m.count === 0);
  const summary =
    months.map((m) => `${formatMonthShort(m.month)} ${m.count}`).join(", ") +
    (gaps.length > 0
      ? `. ${gaps.length} mois sans épreuve : ${gaps.map((m) => formatMonthShort(m.month)).join(", ")}.`
      : ".");

  return (
    <div className="overflow-x-auto">
      <div
        role="img"
        aria-label={`Couverture mensuelle des épreuves : ${summary}`}
        className="flex h-40 items-end gap-1.5"
        style={{ minWidth: `${months.length * 28}px` }}
      >
        {months.map((m) => (
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
              {formatMonthShort(m.month)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

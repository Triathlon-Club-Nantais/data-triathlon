import { scaleLinear } from "d3-scale";
import { formatMonthShort } from "@/lib/utils/date";

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
      <p className="py-8 text-center text-sm text-[var(--tcn-text-faint)]">
        Pas encore de données mensuelles.
      </p>
    );
  }

  const max = Math.max(1, ...entries.map(([, v]) => v));

  // d3-scale ne fait que la partie linéaire (0→max sur 0→100) ; le plancher de
  // 4 % pour rester visible à zéro reste un `Math.max` explicite au point
  // d'usage — ce n'est PAS un `range([4, 100])`, qui décalerait toutes les
  // valeurs intermédiaires (`range([4,100])` donne 52 % pour une valeur moitié
  // du max, pas 50 % : deux formules différentes, pas juste deux écritures).
  const heightScale = scaleLinear().domain([0, max]).range([0, 100]);

  const values = entries.map(([, v]) => v);
  const summary =
    `Activité mensuelle sur ${entries.length} mois, ` +
    `de ${Math.min(...values)} à ${Math.max(...values)} dossards.`;

  return (
    <div
      role="img"
      aria-label={summary}
      className="flex h-44 items-end gap-1.5"
    >
      {entries.map(([key, value], index) => (
        <div key={key} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
          {/* Valeur toujours écrite : `opacity-0` + `group-hover` n'existent pas
              au doigt, et l'attribut `title` non plus (WCAG 1.4.13, #480). */}
          <span aria-hidden className="num text-[11px] font-bold text-[var(--tcn-text-faint)]">
            {value}
          </span>
          <div
            className="w-full rounded-t-sm bg-[color-mix(in_oklch,var(--primary)_70%,transparent)]"
            style={{ height: `${Math.max(4, heightScale(value))}%` }}
          />
          {/* Un mois sur deux, compté depuis la fin pour que le plus récent soit
              toujours écrit : douze libellés de 11px ne tiennent pas sur 287px. */}
          <span aria-hidden data-month-label className="micro-label text-[var(--tcn-text-faint)]">
            {(entries.length - 1 - index) % 2 === 0 ? formatMonthShort(key) : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

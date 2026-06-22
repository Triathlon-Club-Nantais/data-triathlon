import { cn } from "@/lib/utils";

/**
 * SPLIT — KPI. Valeur en mono tabulaire 34px/800, libellé micro-capitales,
 * tendance ▲/▼ (success/destructive). Sans équivalent shadcn → composant custom.
 */
export function Stat({
  value,
  label,
  sub,
  trend,
  accent = false,
  className,
}: {
  value: React.ReactNode;
  label: string;
  sub?: React.ReactNode;
  /** Variation : >= 0 → success (▲), < 0 → destructive (▼). */
  trend?: number;
  /** Met la valeur en accent lisible (`--accent-ink`). */
  accent?: boolean;
  className?: string;
}) {
  return (
    <div className={className}>
      <div
        className={cn(
          "num text-[34px] leading-none font-extrabold tracking-[-0.01em]",
          accent ? "text-accent-ink" : "text-foreground",
        )}
      >
        {value}
      </div>
      <div className="mt-[7px] flex items-center gap-[7px] text-xs text-muted-foreground">
        <span className="uppercase tracking-[0.06em]">{label}</span>
        {trend != null && (
          <span
            className={cn(
              "num text-[11px] font-bold",
              trend >= 0 ? "text-success" : "text-destructive",
            )}
          >
            {trend >= 0 ? "▲" : "▼"} {Math.abs(trend)}
          </span>
        )}
      </div>
      {sub && <div className="mt-0.5 text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

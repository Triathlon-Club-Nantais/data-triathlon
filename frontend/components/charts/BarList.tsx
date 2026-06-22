import { EmptyState } from "@/components/ui/empty-state";

/** Liste de barres horizontales (répartition par catégorie). Server-compatible. */
export function BarList({
  entries,
  labeller,
  colorer,
  emptyTitle = "Aucune donnée",
}: {
  entries: [string, number][];
  labeller: (key: string) => string;
  colorer?: (key: string) => string;
  emptyTitle?: string;
}) {
  if (entries.length === 0) {
    return (
      <EmptyState title={emptyTitle} className="border-0 py-8 ring-0 shadow-none" />
    );
  }
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="space-y-2.5">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-center gap-3">
          <span className="w-36 shrink-0 truncate text-sm" title={labeller(key)}>
            {labeller(key)}
          </span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full transition-[width] duration-500"
              style={{
                width: `${(value / max) * 100}%`,
                background: colorer ? colorer(key) : "var(--accent-ink)",
              }}
            />
          </div>
          <span className="num w-10 text-right text-sm font-bold">{value}</span>
        </div>
      ))}
    </div>
  );
}

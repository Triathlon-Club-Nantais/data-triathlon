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
  // Plancher de largeur : sur /club l'étendue va de 1 à 279, soit 0,36 % pour la
  // plus petite barre. L'échelle reste **linéaire** — une racine ferait lire ce
  // rapport de 279 comme un rapport de 17, que le chiffre à droite dément — et
  // c'est seulement la visibilité de la barre qu'on garantit.
  const MIN_BAR_WIDTH = 2;
  const summary = entries
    .map(([key, value]) => `${labeller(key)} ${value}`)
    .join(", ");
  return (
    <div
      role="img"
      aria-label={`Répartition sur ${entries.length} entrées : ${summary}.`}
      className="space-y-2.5"
    >
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-center gap-3">
          <span aria-hidden className="w-36 shrink-0 truncate text-sm" title={labeller(key)}>
            {labeller(key)}
          </span>
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              data-bar
              className="h-full rounded-full"
              style={{
                width: `${Math.max(MIN_BAR_WIDTH, (value / max) * 100)}%`,
                background: colorer ? colorer(key) : "var(--accent-ink)",
              }}
            />
          </div>
          <span aria-hidden className="num w-10 text-right text-sm font-bold">{value}</span>
        </div>
      ))}
    </div>
  );
}

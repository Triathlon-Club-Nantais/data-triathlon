import { scaleLinear } from "d3-scale";
import { pctFr } from "@/lib/utils/format";
import { EmptyState } from "@/components/ui/empty-state";

/** « Autres (500) » se dit « Autres » à l'oreille : le compte suit déjà en pourcentage. */
function nomCourt(name: string): string {
  return name.replace(/\s*\(\d+\)$/, "");
}

const CAT_COLORS = [
  "var(--tcn-orange)", "var(--tcn-orange-300)", "var(--tcn-ink)", "var(--tcn-ink-2)",
  "var(--tcn-ink-3)", "var(--tcn-grey-400)", "var(--tcn-orange-200)", "var(--tcn-grey-300)",
];

/**
 * Barres de répartition par catégorie (`/courses/[id]`). `total` est la somme
 * de **toutes** les catégories (`categories_total` de l'API), pas la somme
 * des catégories passées ici — sinon chaque barre se gonfle (cf. page test).
 */
export function CategoryBars({
  categories,
  total,
}: {
  categories: { name: string; count: number }[];
  total: number;
}) {
  if (categories.length === 0) {
    return <EmptyState bare className="px-0 py-4" title="Catégories non renseignées" />;
  }

  const scale = total > 0 ? scaleLinear().domain([0, total]).range([0, 100]) : () => 0;

  // Ce que les barres affichées ne couvrent pas (#486, RES-7). Sur la course 27,
  // les huit barres du top ne portent que 70,1 % des participants — 29,9 %
  // n'apparaissaient nulle part, et l'écran laissait croire à un tout. Omise
  // quand elle est nulle (rien à dessiner) ou négative (le dénominateur publié
  // est incohérent : mieux vaut se taire que mentir dans l'autre sens).
  const reste = total - categories.reduce((somme, c) => somme + c.count, 0);
  const barres =
    reste > 0 ? [...categories, { name: `Autres (${reste})`, count: reste }] : categories;

  const summary = barres.map((c) => `${nomCourt(c.name)} ${pctFr(scale(c.count))} %`).join(", ");

  return (
    <div
      role="img"
      aria-label={`Répartition par catégorie : ${summary}.`}
      style={{ display: "flex", flexDirection: "column", gap: 10 }}
    >
      {barres.map((c, i) => {
        const pct = scale(c.count);
        // La barre « Autres » porte un compte entre parenthèses : elle déborde
        // les 36 px calibrés pour « S1 », d'où la piste élargie pour elle seule.
        const reste = i === categories.length;
        return (
          <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span aria-hidden style={{ flex: "none", width: reste ? "auto" : 36, minWidth: 36, fontWeight: 800, fontSize: 13, color: reste ? "var(--tcn-text-muted)" : "var(--tcn-ink)", whiteSpace: "nowrap" }}>{c.name}</span>
            <div style={{ flex: 1, height: 13, background: "var(--tcn-fill)", borderRadius: 999, overflow: "hidden" }}>
              <div style={{ width: pct + "%", height: "100%", background: CAT_COLORS[i % CAT_COLORS.length], borderRadius: 999 }} />
            </div>
            <span aria-hidden style={{ flex: "none", width: 48, textAlign: "right", fontSize: 13, fontWeight: 700, color: "var(--tcn-text-body)" }}>{pctFr(pct)}%</span>
          </div>
        );
      })}
    </div>
  );
}

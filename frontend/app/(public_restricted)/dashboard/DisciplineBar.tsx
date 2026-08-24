import { pctFr } from "@/lib/utils/format";

interface Part {
  name: string;
  color: string;
  ink: string;
  count: number;
  pct: number;
}

/**
 * Part minimale, en pourcentage, pour qu'un segment puisse porter son nom.
 * En dessous, le libellé serait tronqué à une lettre : c'est la légende qui le
 * nomme, et l'alternative textuelle qui le chiffre.
 */
const LABEL_THRESHOLD = 12;

/**
 * Barre empilée de la répartition par type d'épreuve.
 *
 * La couleur n'y est **pas** le seul encodage (WCAG 1.4.1) : chaque segment
 * assez large écrit son nom, un filet blanc marque les frontières, et la barre
 * entière porte un récapitulatif chiffré. Le filet est un `outline` intérieur
 * et non une `gap` : une gouttière retrancherait de la largeur totale et
 * fausserait les pourcentages qu'on vient d'afficher.
 */
export function DisciplineBar({ disciplines }: { disciplines: Part[] }) {
  if (disciplines.length === 0) return null;

  const summary = disciplines.map((d) => `${d.name} ${pctFr(d.pct)} %`).join(", ");

  return (
    <div
      role="img"
      aria-label={`Répartition des dossards par type d'épreuve : ${summary}.`}
      style={{ display: "flex", height: 24, borderRadius: 999, overflow: "hidden", marginBottom: 24 }}
    >
      {disciplines.map((d) => (
        <div
          key={d.name}
          data-segment={d.name}
          style={{
            width: `${d.pct}%`,
            background: d.color,
            outline: "1px solid var(--tcn-surface)",
            outlineOffset: -1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
            whiteSpace: "nowrap",
          }}
        >
          {d.pct >= LABEL_THRESHOLD && (
            <span
              aria-hidden
              className="micro-label"
              style={{ color: d.ink, padding: "0 6px" }}
            >
              {d.name}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

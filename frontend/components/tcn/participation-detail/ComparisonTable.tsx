import type { ComparisonRow } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { pctFr } from "@/lib/utils/format";
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

const TOTAL_KEY = "total";

/**
 * Comparaison de l'athlète aux positions de référence du classement scratch.
 *
 * Les lignes arrivent déjà filtrées par l'API : une position que l'épreuve
 * n'atteint pas est absente, pas vide. Ce composant ne comble donc rien — un
 * tiret ici signale un temps non publié, jamais un effectif insuffisant.
 */
export function ComparisonTable({
  rows,
  segments,
  eventType,
}: {
  rows: ComparisonRow[];
  segments: string[];
  eventType: string;
}) {
  const columns = splitColumnsFromKeys(eventType, segments);
  const shortSegmentLabels = columns.filter((column) => column.small).map((column) => column.label);

  // Sous 640 px, sept colonnes tombent à ~500 px de large et le tableau défile
  // dans sa carte. Les segments courts sont les premiers à sortir : ils sont
  // déjà rendus en gris atténué, et la note du bas dit déjà que leurs
  // pourcentages sont bruités. Ce n'est pas une mise en conformité — un tableau
  // de données est exempté de WCAG 1.4.10 —, c'est de la lisibilité.
  const classeColonne = (small?: boolean) => (small ? "hidden sm:table-cell" : undefined);

  return (
    <Card style={{ marginBottom: 24, overflowX: "auto" }}>
      <Eyebrow>Comparaison au classement</Eyebrow>
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 14, fontSize: 13 }}>
        <thead>
          <tr>
            {/* Largeur fixe : sans elle, la colonne de position absorbe tout
                l'espace que les colonnes de pourcentage n'occupent pas. */}
            <th style={{ ...headStyle, width: 72, textAlign: "left" }}>Position</th>
            {columns.map((column) => (
              <th
                key={column.key}
                className={classeColonne(column.small)}
                style={{ ...headStyle, color: column.small ? "var(--tcn-text-faint)" : column.color }}
              >
                {column.label}
              </th>
            ))}
            <th style={headStyle}>Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.rank}>
              <th scope="row" style={{ ...cellStyle, textAlign: "left", fontWeight: 700 }}>
                {row.position_label}
              </th>
              {columns.map((column) => (
                <td key={column.key} className={classeColonne(column.small)} style={cellStyle}>
                  {formatPercentage(row.percentages[column.key])}
                </td>
              ))}
              <td style={{ ...cellStyle, fontWeight: 700 }}>
                {formatPercentage(row.percentages[TOTAL_KEY])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {shortSegmentLabels.length > 0 && (
        <p style={{ marginTop: 10, fontSize: 13, color: "var(--tcn-text-faint)" }}>
          Les segments courts ({shortSegmentLabels.join(", ")}) sont sensibles au bruit de
          chronométrage : leurs pourcentages peuvent ne pas décroître régulièrement d&apos;un
          rang à l&apos;autre. Leurs colonnes s&apos;affichent sur un écran plus large.
        </p>
      )}
    </Card>
  );
}

function formatPercentage(value: number | undefined): string {
  return value == null ? "—" : `${pctFr(value)} %`;
}

const headStyle = {
  padding: "8px 10px",
  textAlign: "right",
  fontSize: 11,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: ".04em",
  color: "var(--tcn-text-faint)",
  borderBottom: "1px solid var(--tcn-border)",
} as const;

const cellStyle = {
  padding: "8px 10px",
  textAlign: "right",
  fontFamily: "var(--tcn-font-cond)",
  color: "var(--tcn-text-body)",
  borderBottom: "1px solid var(--tcn-border-faint)",
} as const;

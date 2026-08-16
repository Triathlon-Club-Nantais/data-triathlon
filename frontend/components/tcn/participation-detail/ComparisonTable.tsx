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
  const hasShortSegment = columns.some((column) => column.small);

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
              <th key={column.key} style={{ ...headStyle, color: column.small ? "var(--tcn-text-faint)" : column.color }}>
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
                <td key={column.key} style={cellStyle}>
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
      {hasShortSegment && (
        <p style={{ marginTop: 10, fontSize: 11, color: "var(--tcn-text-faint)" }}>
          Les segments courts (T1, T2) sont sensibles au bruit de chronométrage : leurs
          pourcentages peuvent ne pas décroître régulièrement d&apos;un rang à l&apos;autre.
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

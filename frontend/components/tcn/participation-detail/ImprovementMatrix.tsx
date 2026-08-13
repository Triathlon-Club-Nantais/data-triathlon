import type { ImprovementRow } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

const PERCENTAGES = ["0.5", "1", "2", "5", "10", "25"];

/**
 * Places gagnées au scratch si un segment avait été amélioré d'un pourcentage.
 *
 * Les lignes viennent de l'API telles quelles — un segment que l'athlète n'a
 * pas publié n'y figure pas, et rien n'est comblé ici : afficher une ligne
 * vide donnerait à croire qu'améliorer ce segment ne rapporte rien.
 */
export function ImprovementMatrix({
  rows,
  eventType,
}: {
  rows: ImprovementRow[];
  eventType: string;
}) {
  const labels = new Map(
    splitColumnsFromKeys(
      eventType,
      rows.map((row) => row.segment),
    ).map((column) => [column.key, column.label]),
  );

  return (
    <Card style={{ overflowX: "auto" }}>
      <Eyebrow>Places gagnées par amélioration</Eyebrow>
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 14, fontSize: 13 }}>
        <thead>
          <tr>
            <th style={headStyle}>Segment</th>
            {PERCENTAGES.map((percentage) => (
              <th key={percentage} style={headStyle}>
                {percentage.replace(".", ",")} %
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.segment} data-segment={row.segment}>
              <th scope="row" style={{ ...cellStyle, textAlign: "left", fontWeight: 700 }}>
                {labels.get(row.segment) ?? row.segment}
              </th>
              {PERCENTAGES.map((percentage) => (
                <td key={percentage} style={cellStyle}>
                  {row.gains[percentage] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
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

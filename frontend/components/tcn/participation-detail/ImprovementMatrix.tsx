import type { ImprovementRow } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

const PERCENTAGES = ["0.5", "1", "2", "5", "10", "25"];

/** Énumération française « Natation, T1 et T2 », sans dépendance ajoutée. */
const LIST_FR = new Intl.ListFormat("fr", { style: "long", type: "conjunction" });

/**
 * Places gagnées au scratch si un segment avait été amélioré d'un pourcentage.
 *
 * Le tableau ne garde que les segments qui rapportent au moins une place : une
 * grille de zéros se lisait comme un défaut de calcul plutôt que comme une
 * réponse. Les segments stériles sont énoncés en une phrase sous le tableau —
 * l'information reste, elle cesse d'occuper six colonnes.
 *
 * Les lignes viennent de l'API telles quelles : un segment que l'athlète n'a
 * pas publié n'y figure pas, et rien n'est comblé ici.
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
  const label = (segment: string) => labels.get(segment) ?? segment;

  const gagnants = rows.filter((row) => PERCENTAGES.some((pct) => (row.gains[pct] ?? 0) > 0));
  const steriles = rows.filter((row) => !gagnants.includes(row));

  return (
    <Card style={{ overflowX: "auto" }}>
      <Eyebrow>Où gagner des places</Eyebrow>
      <p style={{ marginTop: 8, fontSize: 13, lineHeight: 1.5, color: "var(--tcn-text-secondary)" }}>
        Places gagnées à l&apos;arrivée si ce segment avait été couru plus vite,
        le reste de la course inchangé.
      </p>

      {gagnants.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 14, fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ ...headStyle, width: 110, textAlign: "left" }}>Segment</th>
              {PERCENTAGES.map((percentage) => (
                <th key={percentage} style={headStyle}>
                  {percentage.replace(".", ",")} %
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {gagnants.map((row) => (
              <tr key={row.segment} data-segment={row.segment}>
                <th scope="row" style={{ ...cellStyle, textAlign: "left", fontWeight: 700 }}>
                  {label(row.segment)}
                </th>
                {PERCENTAGES.map((percentage) => (
                  <td key={percentage} style={cellStyle}>
                    {formatGain(row.gains[percentage])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {steriles.length > 0 && (
        <p style={{ marginTop: 14, fontSize: 13, color: "var(--tcn-text-faint)" }}>
          {LIST_FR.format(steriles.map((row) => label(row.segment)))} : aucune place
          gagnée, même 25 % plus vite.
        </p>
      )}
    </Card>
  );
}

/**
 * Un gain se lit comme un delta, d'où le signe. Un gain nul devient un point
 * médian : le zéro attirait l'œil autant qu'un vrai gain.
 */
function formatGain(gain: number | undefined): string {
  if (gain == null) return "—";
  return gain > 0 ? `+${gain}` : "·";
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

import type { ComparisonRow } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { pctFr } from "@/lib/utils/format";
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

const TOTAL_KEY = "total";

// Sous 640 px, sept colonnes tombent à ~500 px de large et le tableau défile
// dans sa carte. Les segments courts sont les premiers à sortir : ils sont
// déjà rendus en gris atténué, et la note du bas dit déjà que leurs
// pourcentages sont bruités. Ce n'est pas une mise en conformité — un tableau
// de données est exempté de WCAG 1.4.10 —, c'est de la lisibilité. Au niveau
// module, comme son jumeau `classePalier` (`ImprovementMatrix.tsx`) : il ne
// capture rien du scope du composant.
const classeColonne = (small?: boolean) => (small ? "hidden sm:table-cell" : undefined);

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
                  <DeltaSeconds mine={row.mine_seconds?.[column.key]} theirs={row.theirs_seconds?.[column.key]} />
                </td>
              ))}
              <td style={{ ...cellStyle, fontWeight: 700 }}>
                {formatPercentage(row.percentages[TOTAL_KEY])}
                <DeltaSeconds mine={row.mine_seconds?.[TOTAL_KEY]} theirs={row.theirs_seconds?.[TOTAL_KEY]} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {shortSegmentLabels.length > 0 && (
        <p style={{ marginTop: 10, fontSize: 13, color: "var(--tcn-text-faint)" }}>
          Les segments courts ({shortSegmentLabels.join(", ")}) sont sensibles au bruit de
          chronométrage : leurs pourcentages peuvent ne pas décroître régulièrement d&apos;un
          rang à l&apos;autre.{" "}
          {/* Seule cette phrase est fausse dès 640 px, où les colonnes sont déjà
              visibles : la phrase sur le bruit de chronométrage, elle, reste
              vraie à toute largeur. */}
          <span className="sm:hidden">Leurs colonnes s&apos;affichent sur un écran plus large.</span>
        </p>
      )}
    </Card>
  );
}

function formatPercentage(value: number | undefined): string {
  return value == null ? "—" : `${pctFr(value)} %`;
}

/**
 * Écart brut en secondes sous le pourcentage — représentation visuelle en
 * plus du ratio, un « 128 % » ne dit rien du temps réellement perdu (US4,
 * #466). Une barre marque l'ampleur de l'écart ; le texte porte le signe.
 */
function DeltaSeconds({ mine, theirs }: { mine: number | undefined; theirs: number | undefined }) {
  if (mine == null || theirs == null) return null;
  const delta = mine - theirs;
  const width = Math.min(100, (Math.abs(delta) / theirs) * 100 * 4);
  return (
    <div style={{ marginTop: 3 }}>
      <div
        aria-hidden
        style={{
          height: 3,
          width: `${width}%`,
          marginLeft: "auto",
          background: delta > 0 ? "var(--tcn-orange)" : "var(--tcn-text-faint)",
          borderRadius: 2,
        }}
      />
      <span style={{ fontSize: 11, color: "var(--tcn-text-faint)" }}>{formatDeltaSeconds(delta)}</span>
    </div>
  );
}

function formatDeltaSeconds(delta: number): string {
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "";
  const abs = Math.round(Math.abs(delta));
  const minutes = Math.floor(abs / 60);
  const seconds = abs % 60;
  if (minutes === 0) return `${sign}${seconds} s`;
  if (seconds === 0) return `${sign}${minutes} min`;
  return `${sign}${minutes} min ${seconds} s`;
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

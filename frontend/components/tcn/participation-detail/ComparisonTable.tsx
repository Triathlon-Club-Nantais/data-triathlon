import type { ComparisonRow, MedianRow, Participation } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { pctFr } from "@/lib/utils/format";
import { secondsFromHms } from "@/lib/utils/time";
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

// #657 : les pourcentages n'indiquaient à aucun endroit à quoi ils se
// comparaient. Un `title` natif suffit ici — ce sont des cellules de texte
// inertes, pas des commandes qu'il faudrait rendre focalisables au clavier.
const TITRE_POSITION =
  "Position de référence au classement scratch, ou médiane des classés, à laquelle le temps de l'athlète est comparé.";
const titreSegment = (label: string) =>
  `Temps de l'athlète sur ${label.toLowerCase()}, en pourcentage du temps de référence de la ligne, position ou médiane (100 % = temps identique, plus de 100 % = plus lent).`;
const TITRE_TOTAL =
  "Temps de l'athlète sur l'ensemble de l'épreuve, en pourcentage du temps de référence de la ligne, position ou médiane (100 % = temps identique, plus de 100 % = plus lent).";

/**
 * Comparaison de l'athlète aux positions de référence du classement scratch,
 * puis aux médianes des classés (#1362).
 *
 * Les lignes arrivent déjà filtrées par l'API : une position que l'épreuve
 * n'atteint pas est absente, pas vide, et une médiane sous l'effectif minimal
 * aussi. Un tiret signale un temps que l'athlète n'a pas publié, ou, sur une
 * médiane seulement, un segment publié par trop peu de classés.
 */
export function ComparisonTable({
  rows,
  medians = [],
  segments,
  eventType,
  athlete,
}: {
  rows: ComparisonRow[];
  medians?: MedianRow[];
  segments: string[];
  eventType: string;
  athlete: Pick<Participation, "splits" | "total_time">;
}) {
  const columns = splitColumnsFromKeys(eventType, segments);
  const shortSegmentLabels = columns.filter((column) => column.small).map((column) => column.label);
  const lines: {
    key: string;
    label: string;
    row: ComparisonRow | MedianRow;
    sampleSize?: number;
    separator?: { borderTop: string };
  }[] = [
    ...rows.map((row) => ({ key: `rang-${row.rank}`, label: row.position_label, row })),
    ...medians.map((row, index) => ({
      key: row.kind,
      label: row.label,
      row,
      sampleSize: row.sample_size,
      // Un filet sous les positions : sans lui, la première médiane se lit comme un rang de plus.
      separator: index === 0 && rows.length > 0 ? { borderTop: "1px solid var(--tcn-border)" } : undefined,
    })),
  ];
  // #1470 : l'API omet aussi une clé de médiane quand l'athlète n'a pas ce
  // temps. Ce tiret-là ne dit rien de l'effectif. `secondsFromHms` rejette au
  // moins tout ce que rejette `to_seconds(strict=True)` côté serveur : l'écart
  // ne peut que taire la note, jamais la faire mentir.
  const athleteHasTime = (key: string) =>
    secondsFromHms(key === TOTAL_KEY ? athlete.total_time : athlete.splits?.[key]) != null;
  const thinSampleLabels = [...columns, { key: TOTAL_KEY, label: "Total" }]
    .filter(({ key }) => athleteHasTime(key) && medians.some((row) => row.percentages[key] == null))
    .map(({ label }) => label);

  return (
    <Card style={{ marginBottom: 24, overflowX: "auto" }}>
      <Eyebrow>Comparaison au classement</Eyebrow>
      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 14, fontSize: 13 }}>
        <thead>
          <tr>
            {/* Largeur fixe : sans elle, la colonne de référence absorbe tout
                l'espace que les colonnes de pourcentage n'occupent pas. */}
            <th style={{ ...headStyle, width: 72, textAlign: "left" }} title={TITRE_POSITION}>
              Référence
            </th>
            {columns.map((column) => (
              <th
                key={column.key}
                className={classeColonne(column.small)}
                style={{ ...headStyle, color: column.small ? "var(--tcn-text-faint)" : column.color }}
                title={titreSegment(column.label)}
              >
                {column.label}
              </th>
            ))}
            <th style={headStyle} title={TITRE_TOTAL}>
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {lines.map(({ key, label, row, sampleSize, separator }) => (
            <tr key={key}>
              <th scope="row" style={{ ...cellStyle, ...separator, textAlign: "left", fontWeight: 700 }}>
                {label}
                {sampleSize != null && <div style={sampleSizeStyle}>{sampleSize} classés</div>}
              </th>
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={classeColonne(column.small)}
                  style={{ ...cellStyle, ...separator, background: pctTint(row.percentages[column.key]) }}
                >
                  {formatPercentage(row.percentages[column.key])}
                  <DeltaSeconds mine={row.mine_seconds?.[column.key]} theirs={row.theirs_seconds?.[column.key]} />
                </td>
              ))}
              <td
                style={{
                  ...cellStyle,
                  ...separator,
                  fontWeight: 700,
                  background: pctTint(row.percentages[TOTAL_KEY]),
                }}
              >
                {formatPercentage(row.percentages[TOTAL_KEY])}
                <DeltaSeconds mine={row.mine_seconds?.[TOTAL_KEY]} theirs={row.theirs_seconds?.[TOTAL_KEY]} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {shortSegmentLabels.length > 0 && (
        <p style={{ marginTop: 10, fontSize: 13, color: "var(--tcn-text-faint)" }}>
          Les segments courts ({shortSegmentLabels.join(", ")}) sont indicatifs : sensibles au
          bruit de chronométrage, leurs pourcentages peuvent varier fortement d&apos;une ligne
          à l&apos;autre.{" "}
          {/* Seule cette phrase est fausse dès 640 px, où les colonnes sont déjà
              visibles : la phrase sur le bruit de chronométrage, elle, reste
              vraie à toute largeur. */}
          <span className="sm:hidden">Leurs colonnes s&apos;affichent sur un écran plus large.</span>
        </p>
      )}
      {thinSampleLabels.length > 0 && (
        <p style={{ marginTop: 10, fontSize: 13, color: "var(--tcn-text-faint)" }}>
          Médiane non calculée pour {thinSampleLabels.join(", ")} : trop peu de classés ont publié{" "}
          {thinSampleLabels.length > 1 ? "ces segments" : "ce segment"}.
        </p>
      )}
    </Card>
  );
}

function formatPercentage(value: number | undefined): string {
  return value == null ? "—" : `${pctFr(value)} %`;
}

// #853 : une barre de taille par cellule d'écart, cumulée sur tout le
// tableau, nuisait à la lisibilité plus qu'elle n'aidait. `pctTint` la
// remplace par un très léger dégradé de fond de cellule (orange = plus lent,
// vert = plus rapide que la référence), plafonné bas pour rester discret —
// même ordre de grandeur que `--tcn-orange-08`/`-12` déjà utilisés ailleurs
// comme fonds de survol. `color-mix()` plutôt qu'un `rgba()` recopiant les
// tokens à la main (patron de `lib/sport-colors.ts`) : une retouche de
// `--tcn-orange`/`--tcn-success` ne peut pas désynchroniser ce fichier en
// silence. Espace `oklab`, comme `sport-colors.ts` : mélanger avec
// `transparent` ne change que l'alpha, jamais la teinte, donc le choix
// d'espace n'affecte pas le rendu ici — il aligne juste ce fichier sur le
// seul espace que verrouille `test/couleur.ts`.
const TEINTE_POURCENTAGE_MAX = 10;
const ECART_POUR_TEINTE_MAX = 50;

export function pctTint(value: number | undefined): string | undefined {
  if (value == null) return undefined;
  const ecart = value - 100;
  if (ecart === 0) return undefined;
  const pourcentage = Math.min(
    TEINTE_POURCENTAGE_MAX,
    (Math.abs(ecart) / ECART_POUR_TEINTE_MAX) * TEINTE_POURCENTAGE_MAX,
  );
  const teinte = ecart > 0 ? "var(--tcn-orange)" : "var(--tcn-success)";
  return `color-mix(in oklab, ${teinte} ${pourcentage.toFixed(2)}%, transparent)`;
}

/**
 * Écart brut en secondes sous le pourcentage — représentation textuelle en
 * plus du ratio, un « 128 % » ne dit rien du temps réellement perdu (US4,
 * #466). Le texte porte le signe ; l'ampleur de l'écart se lit désormais dans
 * le fond de cellule (`pctTint`), pas dans une barre dédiée (#853).
 */
function DeltaSeconds({ mine, theirs }: { mine: number | undefined; theirs: number | undefined }) {
  if (mine == null || theirs == null) return null;
  const delta = mine - theirs;
  return (
    <div style={{ marginTop: 3 }}>
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

const sampleSizeStyle = {
  marginTop: 3,
  fontSize: 11,
  fontWeight: 400,
  color: "var(--tcn-text-faint)",
  whiteSpace: "nowrap",
} as const;

const cellStyle = {
  padding: "8px 10px",
  textAlign: "right",
  fontFamily: "var(--tcn-font-cond)",
  color: "var(--tcn-text-body)",
  borderBottom: "1px solid var(--tcn-border-faint)",
} as const;

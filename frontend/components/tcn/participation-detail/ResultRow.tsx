import type { Participation } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { genderShort } from "@/lib/utils/format";
// Imports directs plutôt que via le barrel `@/components/tcn`, qui réexporte
// ce composant : le cycle ne se verrait qu'au build.
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";
import { PlaceBadge } from "../PlaceBadge";

/**
 * En-tête de la page de détail : le résultat de l'athlète, segment par segment.
 *
 * `segments` vient de l'API et non des splits de la participation : c'est la
 * liste publiée par l'**épreuve**. Un athlète auquel il manque un segment que
 * les autres ont doit garder sa colonne, avec un tiret dedans.
 */
export function ResultRow({
  participation,
  segments,
}: {
  participation: Participation;
  segments: string[];
}) {
  const columns = splitColumnsFromKeys(participation.course?.event_type ?? "", segments);
  const splits = participation.splits ?? {};
  const name = [participation.athlete?.nom, participation.athlete?.prenom]
    .filter(Boolean)
    .join(" ");

  return (
    <Card style={{ marginBottom: 24 }}>
      <Eyebrow>Ma performance</Eyebrow>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 18,
          flexWrap: "wrap",
          margin: "12px 0 22px",
        }}
      >
        {participation.rank_overall != null ? (
          <PlaceBadge place={participation.rank_overall} style={{ fontSize: 22, minWidth: 44 }} />
        ) : (
          <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
        )}
        <div
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: "clamp(22px, 4vw, 32px)",
            color: "var(--tcn-ink)",
            lineHeight: 1,
          }}
        >
          {name}
        </div>
        <div style={{ display: "flex", gap: 14, fontSize: 13, color: "var(--tcn-text-body)" }}>
          <span>{participation.category ?? "—"}</span>
          <span>{genderShort(participation.athlete?.gender)}</span>
        </div>
        <div
          style={{
            marginLeft: "auto",
            fontFamily: "var(--tcn-font-cond)",
            fontWeight: 700,
            fontSize: 24,
            color: "var(--tcn-ink)",
          }}
        >
          {participation.total_time ?? "—"}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))`,
          gap: 12,
        }}
      >
        {columns.map((column) => (
          <div
            key={column.key}
            data-segment={column.key}
            data-transition={String(Boolean(column.small))}
            style={{
              padding: "10px 12px",
              borderRadius: "var(--tcn-radius-md)",
              background: column.small ? "transparent" : "var(--tcn-fill)",
              border: column.small ? "1px dashed var(--tcn-border)" : "1px solid var(--tcn-border)",
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: ".04em",
                color: column.small ? "var(--tcn-text-faint)" : column.color,
              }}
            >
              {column.label}
            </div>
            <div
              style={{
                fontFamily: "var(--tcn-font-cond)",
                fontWeight: column.small ? 400 : 700,
                fontSize: column.small ? 15 : 18,
                color: column.small ? "var(--tcn-grey-400)" : "var(--tcn-ink)",
              }}
            >
              {splits[column.key] ?? "—"}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

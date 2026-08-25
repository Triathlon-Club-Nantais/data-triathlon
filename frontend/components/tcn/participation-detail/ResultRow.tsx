import Link from "next/link";
import type { CSSProperties } from "react";
import type { Participation, RankingEvolutionStep } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { genderShort, ordinalFr } from "@/lib/utils/format";
// Imports directs plutôt que via le barrel `@/components/tcn`, qui réexporte
// ce composant : le cycle ne se verrait qu'au build.
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";
import { PendingBadge } from "../PendingBadge";
import { PlaceBadge } from "../PlaceBadge";

/**
 * En-tête de la page de détail : le résultat de l'athlète, segment par segment.
 *
 * `segments` vient de l'API et non des splits de la participation : c'est la
 * liste publiée par l'**épreuve**. Un athlète auquel il manque un segment que
 * les autres ont doit garder sa colonne, avec un tiret dedans.
 *
 * `steps` n'y sert qu'à une chose : la position sur le segment isolé, celle
 * que le graphique met en barres. Un segment que le classement n'a pas pu
 * établir n'affiche rien — un tiret à cet endroit se lirait comme un dernier
 * rang.
 */
export function ResultRow({
  participation,
  segments,
  steps,
}: {
  participation: Participation;
  segments: string[];
  steps: RankingEvolutionStep[];
}) {
  const columns = splitColumnsFromKeys(participation.course?.event_type ?? "", segments);
  const splits = participation.splits ?? {};
  const positions = new Map(steps.map((step) => [step.segment, step.segment_position]));
  const name = [participation.athlete?.nom, participation.athlete?.prenom]
    .filter(Boolean)
    .join(" ");

  const secondaryRanks = [
    { label: "cat.", value: participation.rank_category },
    { label: "genre", value: participation.rank_gender },
  ].filter((rank): rank is { label: string; value: number } => rank.value != null);

  return (
    <Card style={{ marginBottom: 24 }}>
      <Eyebrow>Résultat</Eyebrow>
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
        {secondaryRanks.length > 0 && (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 2,
              fontSize: 12,
              fontWeight: 700,
              color: "var(--tcn-text-faint)",
            }}
          >
            {secondaryRanks.map((rank) => (
              <span key={rank.label}>
                {ordinalFr(rank.value)} {rank.label}
              </span>
            ))}
          </div>
        )}
        <Link
          href={`/athletes/${participation.athlete?.id}`}
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: "clamp(22px, 4vw, 32px)",
            color: "var(--tcn-ink)",
            lineHeight: 1,
          }}
        >
          {name}
        </Link>
        {participation.is_pending_validation && (
          <PendingBadge rejected={participation.is_rejected} />
        )}
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
        className="result-segments-grid"
        style={{ "--segments-count": columns.length } as CSSProperties}
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
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
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
              {positions.has(column.key) && (
                <div
                  data-position=""
                  style={{
                    fontFamily: "var(--tcn-font-cond)",
                    fontWeight: 700,
                    fontSize: 12,
                    color: "var(--tcn-text-faint)",
                  }}
                >
                  {ordinalFr(positions.get(column.key) as number)}
                </div>
              )}
            </div>
            <div
              data-time=""
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

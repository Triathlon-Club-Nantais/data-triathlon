import { arc, pie, type PieArcDatum } from "d3-shape";
import { pctFr } from "@/lib/utils/format";

const SIZE = 130;
const OUTER_R = SIZE / 2;
// Reprend l'épaisseur de l'ancien anneau CSS (`inset: 26` sur un disque de 130).
const RING_THICKNESS = 26;
const INNER_R = OUTER_R - RING_THICKNESS;

interface GenderSlice {
  label: "Homme" | "Femme";
  value: number;
}

const SLICE_COLOR: Record<GenderSlice["label"], string> = {
  Homme: "var(--tcn-orange)",
  Femme: "var(--tcn-ink)",
};

const pieLayout = pie<GenderSlice>()
  .sort(null)
  .value((d) => d.value);

const arcGenerator = arc<PieArcDatum<GenderSlice>>()
  .innerRadius(INNER_R)
  .outerRadius(OUTER_R);

/**
 * Donut de répartition hommes/femmes (`/courses/[id]`). Remplace le
 * dégradé CSS (`conic-gradient`) par un `<path>` par tranche : chacune porte
 * sa propre alternative textuelle, que le dégradé ne pouvait pas offrir.
 */
export function GenderDonut({
  malePct,
  femalePct,
  hasGender,
}: {
  malePct: number;
  femalePct: number;
  hasGender: boolean;
}) {
  const slices = hasGender
    ? pieLayout([
        { label: "Homme", value: malePct },
        { label: "Femme", value: femalePct },
      ])
    : [];

  return (
    <>
      <div style={{ position: "relative", width: SIZE, height: SIZE }}>
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE} style={{ display: "block" }}>
          <g transform={`translate(${OUTER_R}, ${OUTER_R})`}>
            {slices.length > 0 ? (
              slices.map((slice) => (
                <path
                  key={slice.data.label}
                  d={arcGenerator(slice) ?? undefined}
                  fill={SLICE_COLOR[slice.data.label]}
                  role="img"
                  aria-label={`${slice.data.label} : ${pctFr(slice.data.value)}%`}
                />
              ))
            ) : (
              <circle r={OUTER_R} fill="var(--tcn-grey-300)" />
            )}
          </g>
        </svg>
        <div
          style={{
            position: "absolute",
            inset: RING_THICKNESS,
            borderRadius: 999,
            background: "var(--tcn-surface)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
          }}
        >
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", lineHeight: 1 }}>
            {Math.round(malePct)}%
          </div>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", color: "var(--tcn-text-faint)", letterSpacing: ".05em" }}>
            Hommes
          </div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
        <Legend color="var(--tcn-orange)" label="Homme" value={`${pctFr(malePct)}%`} />
        <Legend color="var(--tcn-ink)" label="Femme" value={`${pctFr(femalePct)}%`} />
      </div>
    </>
  );
}

function Legend({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
      <span style={{ width: 10, height: 10, borderRadius: 3, background: color }} />
      <span style={{ color: "var(--tcn-text-body)" }}>{label}</span>
      <b style={{ marginLeft: "auto", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>{value}</b>
    </div>
  );
}

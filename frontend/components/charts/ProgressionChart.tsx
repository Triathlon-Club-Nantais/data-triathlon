import { scaleLinear } from "d3-scale";
import { line as d3Line, curveMonotoneX } from "d3-shape";
import type { ProgressionPoint } from "@/lib/utils/ranking";
import { formatDate } from "@/lib/utils/date";

// Système de coordonnées horizontal seulement : le SVG s'étire à la largeur
// disponible (`preserveAspectRatio="none"`), une abscisse ne vaut donc qu'en
// pourcentage de W. H est en pixels réels, pour que les libellés HTML
// s'alignent sur la géométrie sans connaître la largeur rendue (#480, RESP-2).
const W = 900;
const H = 200;
const TOP = 12;
const BOTTOM = 160;
const BOTTOM_GUTTER = 24;

// Sous ce seuil, une tendance ne se lit pas — deux points relient toujours
// une droite, trois sont le minimum pour distinguer une évolution d'un bruit.
const MIN_POINTS = 3;

/**
 * Évolution du ratio de performance (place / nombre de classés) d'un athlète
 * à travers ses participations. Plus le ratio est petit, meilleure est la
 * performance : l'axe est inversé, le meilleur ratio en haut — même
 * convention que `RankingEvolutionChart`.
 *
 * Rendu serveur pur : aucun état, aucune hydratation nécessaire.
 */
export function ProgressionChart({ points }: { points: ProgressionPoint[] }) {
  if (points.length < MIN_POINTS) {
    return (
      <p className="py-8 text-center text-sm text-[var(--tcn-text-faint)]">
        Pas encore assez d&apos;épreuves pour tracer une progression (3 minimum).
      </p>
    );
  }

  const percents = points.map((p) => p.percent);
  const best = Math.min(...percents);
  const worst = Math.max(...percents);
  const margin = Math.max(1, Math.round((worst - best) * 0.15));
  const top = Math.max(0, best - margin);
  const bottom = worst + margin;

  const yScale = scaleLinear().domain([top, bottom]).range([TOP, BOTTOM]);
  const xOf = (index: number) => (points.length === 1 ? W / 2 : (W / (points.length - 1)) * index);

  const linePoints = points.map((p, index) => ({ x: xOf(index), y: yScale(p.percent) }));
  const line =
    d3Line<{ x: number; y: number }>()
      .x((point) => point.x)
      .y((point) => point.y)
      .curve(curveMonotoneX)(linePoints) ?? "";

  const summary = points
    .map((p) => `${formatDate(p.eventDate)} top ${p.percent} pour cent`)
    .join(", ");

  return (
    <div style={{ position: "relative", paddingBottom: BOTTOM_GUTTER }}>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ width: "100%", height: H, display: "block" }}
        role="img"
        aria-label={`Évolution du ratio de performance : ${summary}.`}
      >
        <path d={line} fill="none" stroke="var(--tcn-orange)" strokeWidth={2.5} vectorEffect="non-scaling-stroke" />
        {points.map((p, index) => (
          <circle
            key={p.participationId}
            data-point={p.participationId}
            cx={xOf(index)}
            cy={yScale(p.percent)}
            r={5}
            fill="var(--tcn-orange)"
          />
        ))}
      </svg>

      {/* Rangée des libellés de date, en HTML : un <text> SVG dans ce viewBox
          étiré tomberait à ~3,5 px sur un iPhone SE (#480, RESP-2). Sa largeur
          épouse celle du SVG, condition pour qu'un pourcentage de `left` se
          résolve juste. */}
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: BOTTOM_GUTTER }}>
        {points.map((p, index) => (
          <span
            key={p.participationId}
            aria-hidden
            style={{
              position: "absolute",
              left: `calc(${(xOf(index) / W) * 100}% - 50% / ${points.length})`,
              width: `calc(100% / ${points.length})`,
              textAlign: "center",
              fontSize: 11,
              lineHeight: "14px",
              color: "var(--tcn-text-faint)",
              fontFamily: "var(--tcn-font-body)",
              whiteSpace: "nowrap",
            }}
          >
            {formatDate(p.eventDate)}
          </span>
        ))}
      </div>
    </div>
  );
}

import { scaleLinear } from "d3-scale";
import { line as d3Line, curveLinear } from "d3-shape";
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

// Gouttières en pixels, hors du SVG : la colonne des graduations à gauche
// (mêmes valeurs que `RankingEvolutionChart`, #677), la rangée date + pourcentage
// en bas — deux lignes désormais, d'où le gabarit repris de ce même composant.
const LEFT_GUTTER = 40;
const BOTTOM_GUTTER = 34;

// Nombre de graduations de l'axe des pourcentages, bornes comprises.
const TICKS = 3;

// Sous ce seuil, une tendance ne se lit pas — deux points relient toujours
// une droite, trois sont le minimum pour distinguer une évolution d'un bruit.
const MIN_POINTS = 3;

/**
 * Évolution du ratio de performance (place / nombre de classés) d'un athlète
 * à travers ses participations. Plus le ratio est petit, meilleure est la
 * performance : l'axe est inversé, le meilleur ratio en haut — même
 * convention que `RankingEvolutionChart`.
 *
 * Rendu serveur pur : aucun état, aucune hydratation nécessaire. Le pourcentage
 * de chaque point est donc écrit en permanence (#677) plutôt que réservé à une
 * infobulle au survol, qui exigerait un composant client.
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
  // `percent` ne dépasse jamais 100 (`rankRatio` refuse rank > total) : sans
  // ce plafond, un dernier de course affiche une graduation « 114 % » (#677,
  // revue de code — la marge ajoutée à `worst` n'était bornée que d'un côté).
  const bottom = Math.min(100, worst + margin);

  const yScale = scaleLinear().domain([top, bottom]).range([TOP, BOTTOM]);
  const xOf = (index: number) => (points.length === 1 ? W / 2 : (W / (points.length - 1)) * index);

  const linePoints = points.map((p, index) => ({ x: xOf(index), y: yScale(p.percent) }));
  // Tracé droit, pas lissé (#677) : avec 3 à quelques points seulement, une
  // courbe lissée (l'ancien `curveMonotoneX`) dessine un creux ou un sommet
  // qui n'existe pas dans les données — un artefact de la spline, pas une
  // tendance réelle.
  const line =
    d3Line<{ x: number; y: number }>()
      .x((point) => point.x)
      .y((point) => point.y)
      .curve(curveLinear)(linePoints) ?? "";

  // Graduations de l'axe des pourcentages, réparties entre les deux bornes du
  // domaine — sans elles, la courbe montrait un sens de variation sans jamais
  // dire de quel pourcentage à quel pourcentage (#677). S'appuie sur
  // `percent` ∈ [1, 100] (`rankRatio`) pour que `bottom - top` ≥ 2 et que les
  // TICKS graduations restent distinctes ; rien ne l'impose au niveau du type.
  const ticks = Array.from({ length: TICKS }, (_, index) =>
    Math.round(top + ((bottom - top) * index) / (TICKS - 1)),
  );

  const summary = points
    .map((p) => `${formatDate(p.eventDate)} top ${p.percent} pour cent`)
    .join(", ");

  return (
    <div>
      <p style={{ marginBottom: 12, fontSize: 13, color: "var(--tcn-text-faint)" }}>
        Classement au sein du peloton à chaque épreuve — plus haut, meilleur.
      </p>
      <div style={{ position: "relative", paddingLeft: LEFT_GUTTER, paddingBottom: BOTTOM_GUTTER }}>
        {/* Graduations, en px réels : un <text> SVG dans ce viewBox étiré non
            uniformément tomberait à ~3,5 px sur un iPhone SE (#480, RESP-2). */}
        {ticks.map((percent) => (
          <span
            key={percent}
            data-tick=""
            aria-hidden
            style={{
              position: "absolute",
              left: 0,
              top: yScale(percent) - 7,
              width: LEFT_GUTTER - 10,
              textAlign: "right",
              fontSize: 12,
              lineHeight: "14px",
              color: "var(--tcn-text-faint)",
            }}
          >
            {percent} %
          </span>
        ))}

        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          style={{ width: "100%", height: H, display: "block" }}
          role="img"
          aria-label={`Évolution du classement au sein du peloton (plus petit, meilleur) : ${summary}.`}
        >
          {ticks.map((percent) => (
            <line
              key={percent}
              x1={0}
              y1={yScale(percent)}
              x2={W}
              y2={yScale(percent)}
              stroke="var(--tcn-border-faint)"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          <path d={line} fill="none" stroke="var(--tcn-orange)" strokeWidth={2.5} vectorEffect="non-scaling-stroke" />
        </svg>

        {/* Points de la courbe, en HTML : un <circle> dans un viewBox étiré non
            uniformément rendrait une ellipse (même défaut déjà corrigé sur
            `RankingEvolutionChart`, #480, fix B). Rangée dédiée dont la largeur
            épouse celle du SVG, condition pour qu'un pourcentage de `left` se
            résolve juste. */}
        <div style={{ position: "absolute", left: LEFT_GUTTER, right: 0, top: 0, height: H, pointerEvents: "none" }}>
          {points.map((p, index) => (
            <span
              key={p.participationId}
              data-point={p.participationId}
              aria-hidden
              style={{
                position: "absolute",
                left: `calc(${(xOf(index) / W) * 100}% - 5px)`,
                top: yScale(p.percent) - 5,
                width: 10,
                height: 10,
                borderRadius: 999,
                background: "var(--tcn-orange)",
              }}
            />
          ))}
        </div>

        {/* Rangée des libellés, en HTML pour la même raison. Le pourcentage
            de chaque point s'affiche en permanence (#677) : l'infobulle au
            survol n'existe pas au doigt (WCAG 1.4.13), et ce composant reste
            sans état pour rester un rendu serveur pur. `aria-hidden` ici,
            contrairement au libellé bas de `RankingEvolutionChart` : le
            résumé de `aria-label` du SVG répète déjà exactement date et
            pourcentage, doubler l'annonce n'apporterait rien à l'oreille. */}
        <div style={{ position: "absolute", left: LEFT_GUTTER, right: 0, bottom: 0, height: BOTTOM_GUTTER }}>
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
              <b style={{ display: "block", fontSize: 12, lineHeight: "15px", color: "var(--tcn-ink)" }}>
                Top {p.percent} %
              </b>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

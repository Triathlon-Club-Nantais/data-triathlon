import { scaleLinear } from "d3-scale";
import { buildTicks, formatTickLabel } from "@/lib/utils/histogram-ticks";

// Espace de tracé. `W` n'est plus qu'un système de coordonnées horizontal : le
// SVG s'étire à la largeur disponible (`preserveAspectRatio="none"`), donc une
// abscisse ne vaut qu'en **pourcentage** de W. `H`, lui, est en pixels réels —
// la hauteur du SVG est fixée, ce qui permet aux libellés HTML de s'aligner sur
// les ordonnées de la géométrie sans connaître la largeur rendue.
const W = 900;
const H = 200;
const TOP = 12;
const BOTTOM = 188;
const Y_TICKS = 5;

/**
 * Distribution des temps d'arrivée d'une épreuve.
 *
 * **Le SVG ne porte aucun texte** (#480, RESP-2). Un `<text>` dans un `viewBox`
 * étiré à `width: 100%` est mis à l'échelle avec lui : sur iPhone SE le facteur
 * vaut 0,32 et les graduations tombent à 3,5 px, sans qu'aucune unité CSS ne
 * puisse les en empêcher. Les libellés sont donc du HTML, en px réels, posés
 * autour de la géométrie.
 *
 * Rendu serveur pur : aucun état, aucun survol, aucune hydratation.
 */
export function Histogram({
  bars,
  max,
  startSec,
  bucketSec,
  markerSec,
}: {
  bars: number[];
  max: number;
  startSec: number;
  bucketSec: number;
  /** Temps de l'athlète en secondes, pour un repère sur sa position (US2, #466).
   *  `null`/`undefined`/hors de `[startSec, endSec]` : aucun repère rendu. */
  markerSec?: number | null;
}) {
  const barGap = W / Math.max(1, bars.length);
  const barW = Math.max(4, barGap * 0.72);

  // Domaine [0, max] → pixel [BOTTOM, TOP] (plus de finishers = plus haut).
  // Repli constant si max=0 : scaleLinear diviserait par un domaine nul.
  const yScale = max > 0 ? scaleLinear().domain([0, max]).range([BOTTOM, TOP]) : () => BOTTOM;

  const endSec = startSec + bars.length * bucketSec;
  const xTicks = bars.length > 0 ? buildTicks(startSec, endSec) : [];
  const secToPct = (sec: number) => (((sec - startSec) / bucketSec) * barGap * 100) / W;

  // Graduations Y : position i-basée, PAS yScale(v). `v` est arrondi, et router
  // par l'échelle décale les graduations quand max n'est pas divisible par
  // Y_TICKS — et les collapse toutes à BOTTOM quand max=0. Régression déjà
  // rencontrée, gardée par les tests max=3 / max=0.
  const yTicks = Array.from({ length: Y_TICKS + 1 }, (_, i) => ({
    value: Math.round((max / Y_TICKS) * i),
    y: BOTTOM - (i / Y_TICKS) * (BOTTOM - TOP),
  }));

  const hasMarker =
    markerSec != null && bars.length > 0 && markerSec >= startSec && markerSec <= endSec;
  const markerX = hasMarker ? (secToPct(markerSec!) * W) / 100 : 0;

  const summary =
    bars.length === 0
      ? "Distribution des temps d'arrivée : aucune donnée."
      : `Distribution des temps d'arrivée, de ${formatTickLabel(startSec)} à ` +
        `${formatTickLabel(endSec)}, maximum ${max} finishers sur une tranche.` +
        (hasMarker ? ` Votre temps se situe à ${formatTickLabel(markerSec!)}.` : "");

  return (
    <div role="img" aria-label={summary} style={{ position: "relative", paddingLeft: 34, paddingBottom: 20 }}>
      {/* Graduations Y, en px réels : `top` vaut directement l'ordonnée du
          viewBox, la hauteur du SVG étant fixée à H pixels. */}
      {yTicks.map(({ value, y }) => (
        <span
          key={value + "-" + y}
          data-y-tick
          aria-hidden
          style={{
            position: "absolute",
            left: 0,
            top: y - 7,
            width: 28,
            textAlign: "right",
            fontSize: 11,
            lineHeight: "14px",
            color: "var(--tcn-text-faint)",
            fontFamily: "var(--tcn-font-body)",
          }}
        >
          {value}
        </span>
      ))}

      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        style={{ width: "100%", height: H, display: "block" }}
      >
        {yTicks.map(({ y }) => (
          <line
            key={y}
            x1={0}
            y1={y}
            x2={W}
            y2={y}
            stroke="var(--tcn-border-faint)"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {bars.map((count, i) => {
          const y = yScale(count);
          return (
            <rect
              key={i}
              x={i * barGap}
              y={y}
              width={barW}
              height={BOTTOM - y}
              rx="2"
              fill="var(--tcn-orange)"
            />
          );
        })}
        {xTicks.map((tickSec) => (
          <line
            key={tickSec}
            x1={(secToPct(tickSec) * W) / 100}
            y1={TOP}
            x2={(secToPct(tickSec) * W) / 100}
            y2={BOTTOM}
            stroke="var(--tcn-border-faint)"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {hasMarker && (
          <line
            data-athlete-marker
            x1={markerX}
            y1={TOP}
            x2={markerX}
            y2={BOTTOM}
            stroke="var(--tcn-ink)"
            strokeWidth={2}
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>

      {/* Libellé du repère, dans une rangée dont la largeur épouse celle du
          SVG (même contrainte que la rangée d'axe X ci-dessous) : `left` s'y
          exprime en pourcentage de `secToPct`, jamais du conteneur padding
          compris. */}
      {hasMarker && (
        <div style={{ position: "absolute", left: 34, right: 0, top: TOP - 18, height: 14 }}>
          <span
            aria-hidden
            style={{
              position: "absolute",
              left: `${secToPct(markerSec!)}%`,
              transform: "translateX(-50%)",
              fontSize: 11,
              fontWeight: 700,
              color: "var(--tcn-ink)",
              fontFamily: "var(--tcn-font-body)",
              whiteSpace: "nowrap",
            }}
          >
            Vous
          </span>
        </div>
      )}

      {/* Rangée des libellés d'axe X. Sa largeur épouse exactement celle du SVG,
          ce qui est la condition pour qu'une abscisse s'exprime en pourcentage.
          Posé sur le conteneur, ce même pourcentage se résoudrait contre la
          largeur padding comprise et décalerait chaque libellé de 34 px × sa
          position — soit la gouttière entière sur la dernière graduation. */}
      <div style={{ position: "absolute", left: 34, right: 0, bottom: 0, height: 20 }}>
        {xTicks.map((tickSec) => (
          <span
            key={tickSec}
            data-x-tick
            aria-hidden
            style={{
              position: "absolute",
              left: `calc(${secToPct(tickSec)}% - 20px)`,
              top: 0,
              width: 40,
              textAlign: "center",
              fontSize: 11,
              lineHeight: "14px",
              color: "var(--tcn-text-faint)",
              fontFamily: "var(--tcn-font-body)",
            }}
          >
            {formatTickLabel(tickSec)}
          </span>
        ))}
      </div>
    </div>
  );
}

"use client";
import { useState } from "react";
import { scaleLinear } from "d3-scale";
import { line as d3Line, curveMonotoneX } from "d3-shape";
import type { RankingEvolutionStep } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

// `WIDTH` n'est plus qu'un système de coordonnées horizontal : le SVG s'étire à
// la largeur disponible (`preserveAspectRatio="none"`), donc une abscisse ne
// vaut qu'en **pourcentage** de WIDTH. `HEIGHT` est en pixels réels — hauteur
// fixée, pour que les libellés HTML s'alignent sur les ordonnées de la
// géométrie sans connaître la largeur rendue (#480, RESP-2).
const WIDTH = 1000;
const HEIGHT = 210;
const PAD = { top: 14, right: 0, bottom: 10, left: 0 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;
const BAR_W = 44;

// Gouttières **en pixels**, hors du SVG : la colonne des graduations à gauche,
// la rangée des libellés d'étape en bas.
const LEFT_GUTTER = 40;
const BOTTOM_GUTTER = 34;

// Nombre de graduations de l'axe des positions, bornes comprises.
const TICKS = 4;

const TOOLTIP_W = 210;
const TOOLTIP_H = 52;

interface Hovered {
  step: RankingEvolutionStep;
  label: string;
  role: "scratch" | "segment";
  x: number;
  y: number;
}

/**
 * Évolution du classement au fil des étapes : position scratch cumulée (ligne)
 * et position sur le segment isolé (barres).
 *
 * SVG écrit à la main, sur le patron de l'histogramme de la page course. Deux
 * séries sur cinq points ne justifient pas une librairie de charting, et le
 * projet n'en embarque aucune.
 *
 * L'axe des ordonnées est **inversé** : la 1re place est en haut. Ses bornes
 * viennent des positions réellement atteintes sur cette course, pas d'une
 * échelle figée — sur un athlète qui oscille entre la 1re et la 4e place, une
 * échelle absolue écraserait toute la lecture.
 */
export function RankingEvolutionChart({
  steps,
  eventType,
}: {
  steps: RankingEvolutionStep[];
  eventType: string;
}) {
  const [hovered, setHovered] = useState<Hovered | null>(null);

  const labels = new Map(
    splitColumnsFromKeys(
      eventType,
      steps.map((s) => s.segment),
    ).map((column) => [column.key, column.label]),
  );

  const positions = steps.flatMap((s) => [s.scratch_position, s.segment_position]);
  const best = Math.min(...positions);
  const worst = Math.max(...positions);
  const margin = Math.max(1, Math.round((worst - best) * 0.15));
  const top = Math.max(1, best - margin);
  const bottom = worst + margin;

  // Position → ordonnée. Domaine [top, bottom] → pixel [PAD.top, PAD.top+PLOT_H] :
  // la meilleure position (top, la plus petite) tombe en haut du graphique.
  // Pas de garde domaine nul ici (contrairement au max=0 de Histogram.tsx,
  // atteignable) : `margin = Math.max(1, ...)` et `bottom = worst + margin`
  // quelques lignes plus haut garantissent toujours `bottom > top`.
  const yScale = scaleLinear().domain([top, bottom]).range([PAD.top, PAD.top + PLOT_H]);
  const yOf = (position: number) => yScale(position);
  const xOf = (index: number) =>
    PAD.left + (PLOT_W / steps.length) * (index + 0.5);

  const linePoints = steps.map((step, index) => ({
    x: xOf(index),
    y: yOf(step.scratch_position),
  }));
  const line =
    d3Line<{ x: number; y: number }>()
      .x((point) => point.x)
      .y((point) => point.y)
      .curve(curveMonotoneX)(linePoints) ?? "";

  // Graduations réparties entre les deux bornes. Sans elles, la courbe montrait
  // un sens de variation sans jamais dire de quelle place à quelle place.
  const ticks = Array.from({ length: TICKS }, (_, index) =>
    Math.round(top + ((bottom - top) * index) / (TICKS - 1)),
  );

  return (
    <Card style={{ marginBottom: 24 }}>
      <Eyebrow>Évolution du classement</Eyebrow>
      <div
        data-legend=""
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 18,
          marginTop: 10,
          fontSize: 12,
          color: "var(--tcn-text-secondary)",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
          <span
            aria-hidden
            style={{ width: 18, height: 3, borderRadius: 2, background: "var(--tcn-orange)" }}
          />
          Classement scratch à la sortie de l&apos;étape
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
          <span
            aria-hidden
            style={{ width: 12, height: 12, borderRadius: 3, background: "var(--tcn-orange-12)" }}
          />
          Position sur le segment seul
        </span>
      </div>
      <div style={{ position: "relative", paddingLeft: LEFT_GUTTER, paddingBottom: BOTTOM_GUTTER, marginTop: 12 }}>
        {/* Graduations de position, en px réels. La 1re place est en haut :
            l'axe est inversé, et ses bornes viennent des positions réellement
            atteintes sur cette course. */}
        {ticks.map((position) => (
          <span
            key={position}
            data-tick=""
            aria-hidden
            style={{
              position: "absolute",
              left: 0,
              top: yOf(position) - 7,
              width: LEFT_GUTTER - 10,
              textAlign: "right",
              fontSize: 12,
              lineHeight: "14px",
              color: "var(--tcn-text-faint)",
            }}
          >
            {position}
          </span>
        ))}

        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          style={{ width: "100%", height: HEIGHT, display: "block" }}
          role="img"
          aria-label="Évolution de la position au fil des étapes"
          onMouseLeave={() => setHovered(null)}
        >
          {ticks.map((position) => (
            <line
              key={position}
              x1={0}
              y1={yOf(position)}
              x2={PLOT_W}
              y2={yOf(position)}
              stroke="var(--tcn-border-faint)"
              vectorEffect="non-scaling-stroke"
            />
          ))}

          {steps.map((step, index) => {
            const label = labels.get(step.segment) ?? step.segment;
            const x = xOf(index);
            const barY = yOf(step.segment_position);
            return (
              <rect
                key={step.segment}
                data-step={step.segment}
                data-role="segment"
                data-y={barY}
                x={x - BAR_W / 2}
                y={barY}
                width={BAR_W}
                height={Math.max(1, PAD.top + PLOT_H - barY)}
                fill="var(--tcn-orange-12)"
                onMouseEnter={() => setHovered({ step, label, role: "segment", x, y: barY })}
              />
            );
          })}

          <path
            d={line}
            fill="none"
            stroke="var(--tcn-orange)"
            strokeWidth={2.5}
            vectorEffect="non-scaling-stroke"
          />

          {hovered && <Tooltip hovered={hovered} />}
        </svg>

        {/* Les points de la courbe sont du HTML : un <circle> dans un viewBox
            étiré non uniformément rendrait une ellipse. Rangée dédiée dont la
            largeur épouse celle du SVG — condition pour qu'un pourcentage de
            `left` retombe juste (même défaut que Histogram, task 5) : posé
            directement sur le conteneur, qui réserve LEFT_GUTTER de gouttière,
            le pourcentage se serait résolu contre sa padding-box et aurait
            dérivé de LEFT_GUTTER × la position. `pointerEvents: none` sur la
            rangée, `auto` sur chaque marqueur : la rangée recouvre tout le
            plot et intercepterait sinon le survol des barres de segment
            dans le SVG en dessous. */}
        <div
          style={{
            position: "absolute",
            left: LEFT_GUTTER,
            right: 0,
            top: 0,
            height: HEIGHT,
            pointerEvents: "none",
          }}
        >
          {steps.map((step, index) => {
            const label = labels.get(step.segment) ?? step.segment;
            const pointY = yOf(step.scratch_position);
            return (
              <span
                key={step.segment}
                data-step={step.segment}
                data-role="scratch"
                data-y={pointY}
                aria-hidden
                onMouseEnter={() =>
                  setHovered({ step, label, role: "scratch", x: xOf(index), y: pointY })
                }
                style={{
                  position: "absolute",
                  left: `calc(${(xOf(index) / WIDTH) * 100}% - 6px)`,
                  top: pointY - 6,
                  width: 12,
                  height: 12,
                  borderRadius: 999,
                  background: "var(--tcn-orange)",
                  pointerEvents: "auto",
                }}
              />
            );
          })}
        </div>

        {/* Nom de l'étape **et sa position**, écrits en permanence : l'infobulle
            au survol n'existe pas au doigt (WCAG 1.4.13, #480). Même rangée
            dédiée que les marqueurs, pour la même raison arithmétique. */}
        <div style={{ position: "absolute", left: LEFT_GUTTER, right: 0, bottom: 0, height: BOTTOM_GUTTER }}>
          {steps.map((step, index) => (
            <span
              key={step.segment}
              data-step-label={step.segment}
              style={{
                position: "absolute",
                left: `calc(${(xOf(index) / WIDTH) * 100}% - 40px)`,
                top: 0,
                width: 80,
                textAlign: "center",
                fontSize: 12,
                lineHeight: "15px",
                color: "var(--tcn-text-faint)",
              }}
            >
              {labels.get(step.segment) ?? step.segment}
              <br />
              <b style={{ color: "var(--tcn-ink)" }}>{step.scratch_position}</b>
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}

/**
 * Infobulle unique — l'état ne retient qu'un élément survolé, jamais une liste.
 * Elle bascule à gauche du point quand elle déborderait à droite du cadre.
 */
function Tooltip({ hovered }: { hovered: Hovered }) {
  const scratch = hovered.role === "scratch";
  const position = scratch ? hovered.step.scratch_position : hovered.step.segment_position;
  const flip = hovered.x + TOOLTIP_W + 12 > WIDTH;
  const x = flip ? hovered.x - TOOLTIP_W - 12 : hovered.x + 12;
  const y = Math.max(0, hovered.y - TOOLTIP_H - 8);

  return (
    <g role="tooltip" pointerEvents="none">
      <rect
        x={x}
        y={y}
        width={TOOLTIP_W}
        height={TOOLTIP_H}
        rx={8}
        fill="var(--tcn-ink)"
        opacity={0.95}
      />
      <text x={x + 12} y={y + 20} fontSize={12} fill="#fff" fontWeight={700}>
        {hovered.label}
      </text>
      <text x={x + 12} y={y + 37} fontSize={12} fill="rgba(255,255,255,.8)">
        {scratch ? "Classement scratch" : "Sur le segment"} : {position}
      </text>
    </g>
  );
}

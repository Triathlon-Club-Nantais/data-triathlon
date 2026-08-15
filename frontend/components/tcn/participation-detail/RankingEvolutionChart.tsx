"use client";
import { useState } from "react";
import { scaleLinear } from "d3-scale";
import { line as d3Line, curveMonotoneX } from "d3-shape";
import type { RankingEvolutionStep } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

// Le SVG prend toute la largeur de la carte : c'est ce rapport, et non une
// hauteur en pixels, qui décide de sa place à l'écran. Un cadre carré occupait
// la moitié d'un écran de portable pour cinq points.
const WIDTH = 1000;
const HEIGHT = 240;
const PAD = { top: 16, right: 16, bottom: 30, left: 54 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;
const BAR_W = 44;

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
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", height: "auto", marginTop: 12 }}
        role="img"
        aria-label="Évolution de la position au fil des étapes"
        onMouseLeave={() => setHovered(null)}
      >
        {ticks.map((position) => (
          <g key={position}>
            <line
              x1={PAD.left}
              y1={yOf(position)}
              x2={PAD.left + PLOT_W}
              y2={yOf(position)}
              stroke="var(--tcn-border-faint)"
            />
            <text
              data-tick=""
              x={PAD.left - 10}
              y={yOf(position) + 4}
              textAnchor="end"
              fontSize={12}
              fill="var(--tcn-text-faint)"
            >
              {position}
            </text>
          </g>
        ))}

        <line
          x1={PAD.left}
          y1={PAD.top}
          x2={PAD.left}
          y2={PAD.top + PLOT_H}
          stroke="var(--tcn-border)"
        />
        <line
          x1={PAD.left}
          y1={PAD.top + PLOT_H}
          x2={PAD.left + PLOT_W}
          y2={PAD.top + PLOT_H}
          stroke="var(--tcn-border)"
        />

        {steps.map((step, index) => {
          const label = labels.get(step.segment) ?? step.segment;
          const x = xOf(index);
          const barY = yOf(step.segment_position);
          return (
            <g key={step.segment}>
              <rect
                data-step={step.segment}
                data-role="segment"
                data-y={barY}
                x={x - BAR_W / 2}
                y={barY}
                width={BAR_W}
                height={Math.max(1, PAD.top + PLOT_H - barY)}
                fill="var(--tcn-orange-12)"
                onMouseEnter={() =>
                  setHovered({ step, label, role: "segment", x, y: barY })
                }
              />
              <text
                x={x}
                y={HEIGHT - 16}
                textAnchor="middle"
                fontSize={12}
                fill="var(--tcn-text-faint)"
              >
                {label}
              </text>
            </g>
          );
        })}

        <path d={line} fill="none" stroke="var(--tcn-orange)" strokeWidth={2.5} />

        {steps.map((step, index) => {
          const label = labels.get(step.segment) ?? step.segment;
          const x = xOf(index);
          const pointY = yOf(step.scratch_position);
          return (
            <circle
              key={step.segment}
              data-step={step.segment}
              data-role="scratch"
              data-y={pointY}
              cx={x}
              cy={pointY}
              r={6}
              fill="var(--tcn-orange)"
              onMouseEnter={() => setHovered({ step, label, role: "scratch", x, y: pointY })}
            />
          );
        })}

        {hovered && <Tooltip hovered={hovered} />}
      </svg>
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

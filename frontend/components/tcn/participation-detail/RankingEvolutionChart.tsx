"use client";
import { useState } from "react";
import type { RankingEvolutionStep } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

const WIDTH = 600;
const HEIGHT = 360;
const PAD = { top: 28, right: 24, bottom: 42, left: 46 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;
const BAR_W = 26;

const TOOLTIP_W = 178;
const TOOLTIP_H = 48;

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

  // Position → ordonnée. `y` croît vers le bas, la meilleure position a le plus
  // petit numéro : la conversion directe met donc bien le 1er en haut.
  const yOf = (position: number) =>
    PAD.top + ((position - top) / Math.max(1, bottom - top)) * PLOT_H;
  const xOf = (index: number) =>
    PAD.left + (PLOT_W / steps.length) * (index + 0.5);

  const line = steps
    .map((step, index) => `${index === 0 ? "M" : "L"} ${xOf(index)} ${yOf(step.scratch_position)}`)
    .join(" ");

  return (
    <Card style={{ marginBottom: 24 }}>
      <Eyebrow>Évolution du classement</Eyebrow>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ width: "100%", height: "auto", marginTop: 12 }}
        role="img"
        aria-label="Évolution de la position au fil des étapes"
        onMouseLeave={() => setHovered(null)}
      >
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

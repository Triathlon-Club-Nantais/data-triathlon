"use client";
import { useState } from "react";
import { scaleLinear } from "d3-scale";
import { line as d3Line, curveMonotoneX } from "d3-shape";
import type { RankingEvolutionStep } from "@/lib/types";
import { splitColumnsFromKeys } from "@/lib/utils/splits";
import { ordinalFr } from "@/lib/utils/format";
import { EmptyState } from "@/components/ui/empty-state";
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

// Dimensions réelles de l'infobulle, en px : posée en HTML (#480, fix B), elle
// n'est plus mise à l'échelle du viewBox — contrairement à l'ancien <text>
// SVG, tombé à 10,3px sur un laptop 1280 avec le rail déplié.
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

  // Sortie anticipée : le backend saute toute étape sans rang
  // (`_ranking_evolution`), donc `steps` peut arriver vide. Sans ce garde,
  // `Math.min(...[])` vaut Infinity et l'échelle produit du NaN (#480, fix C).
  if (steps.length === 0) {
    return (
      <Card style={{ marginBottom: 24 }}>
        <Eyebrow>Évolution du classement</Eyebrow>
        <EmptyState
          bare
          className="px-0 py-8"
          title="Classement par étape indisponible"
          description="Aucune étape de cette épreuve n'a de position enregistrée pour ce coureur."
        />
      </Card>
    );
  }

  const labels = new Map(
    splitColumnsFromKeys(
      eventType,
      steps.map((s) => s.segment),
    ).map((column) => [column.key, column.label]),
  );

  // Récapitulatif chiffré pour `role="img"` (#480, fix D) : patron « X : liste. »
  // partagé avec DisciplineBar/BarList/CategoryBars. Les noms sont mis en
  // minuscule — ce sont des noms communs dans une phrase, pas des titres.
  const summary = steps
    .map((step) => `${(labels.get(step.segment) ?? step.segment).toLowerCase()} ${ordinalFr(step.scratch_position)}`)
    .join(", ");

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
          color: "var(--tcn-text-muted)",
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
      {/* `onMouseLeave` sur le **conteneur**, jamais sur le SVG : les marqueurs
          de courbe sont du HTML posé hors du SVG (voir plus bas), donc en sortir
          ne lui envoie aucun `mouseleave` et l'infobulle restait plaquée sur le
          graphique — indéfiniment au doigt, où le premier tap émet un
          `mouseenter` synthétique et où rien ne repasse jamais sur le SVG. Le
          conteneur est le seul ancêtre commun aux deux déclencheurs (barres
          dans le SVG, marqueurs à côté). */}
      <div
        style={{ position: "relative", paddingLeft: LEFT_GUTTER, paddingBottom: BOTTOM_GUTTER, marginTop: 12 }}
        onMouseLeave={() => setHovered(null)}
      >
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
          aria-label={`Évolution du classement : ${summary}.`}
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
        </svg>

        {/* Infobulle : sortie du SVG (#480, fix B) — un <text> dans un viewBox
            étiré à width:100% se met à l'échelle avec lui et tombait à 10,3px
            sur un laptop 1280 avec le rail déplié. Même rangée que les
            marqueurs pour la conversion abscisse → pourcentage. Posée **avant**
            la rangée des marqueurs, pas après : sinon elle peindrait par-dessus
            eux, et dès que le `clamp()` la plaque sur le bord droit du cadre,
            elle couvrirait entièrement le point qu'elle décrit (mesuré : dernier
            point d'une courbe qui culmine à `top: 0`, infobulle plaquée sur
            [0, 52], point à `top: 2` — recouvert). L'ancien `<text>` SVG vivait
            *dans* le SVG, donc la rangée des marqueurs peignait déjà par-dessus
            lui ; cet ordre rétablit ce même dessus-dessous. `pointerEvents:
            none` : elle ne doit jamais intercepter le survol qui la fait vivre. */}
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
          {hovered && <Tooltip hovered={hovered} />}
        </div>

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
            dédiée que les marqueurs, pour la même raison arithmétique.
            La boîte vaut l'entraxe (`100% / N`), jamais une largeur fixe : à
            80px fixes, cinq étapes sur un iPhone SE (247px de SVG utiles)
            se chevauchent de 31px (#480, revue UI/UX bloquante). Le
            **nom** s'écrête à l'ellipse quand il ne tient pas — un libellé
            de source peut faire trois mots en capitales (« COURSE A PIED »,
            `splitColumnsFromKeys` → `sourceEntry`) — mais la **position**
            ne s'écrête jamais : c'est le chiffre que ce lot vient de rendre
            accessible sans survol, l'écrêter serait revenir en arrière. */}
        <div style={{ position: "absolute", left: LEFT_GUTTER, right: 0, bottom: 0, height: BOTTOM_GUTTER }}>
          {steps.map((step, index) => (
            <span
              key={step.segment}
              data-step-label={step.segment}
              style={{
                position: "absolute",
                left: `calc(${(xOf(index) / WIDTH) * 100}% - 50% / ${steps.length})`,
                top: 0,
                width: `calc(100% / ${steps.length})`,
                textAlign: "center",
                fontSize: 12,
                lineHeight: "15px",
                color: "var(--tcn-text-faint)",
              }}
            >
              {/* `textAlign: "left"` sur ce seul span : centré, un texte écrêté
                  à l'ellipse est rogné des deux côtés et ne reçoit l'ellipse
                  qu'à droite — le début disparaît sans aucun marqueur visuel
                  (même défaut déjà corrigé sur `DisciplineBar`, ce lot doit
                  rester cohérent avec lui-même). Aligné à gauche, seule la fin
                  se perd, et l'ellipse la signale. La position, elle, reste
                  centrée et entière : elle n'est jamais écrêtée. */}
              <span
                style={{
                  display: "block",
                  textAlign: "left",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {labels.get(step.segment) ?? step.segment}
              </span>
              <b style={{ display: "block", color: "var(--tcn-ink)" }}>{step.scratch_position}</b>
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}

/**
 * Infobulle unique — l'état ne retient qu'un élément survolé, jamais une liste.
 *
 * `hovered.x` est une abscisse de viewBox : convertie en pourcentage de la
 * rangée (largeur = celle du SVG rendu), elle se pose en HTML sans connaître
 * la largeur réelle. `clamp()` la borne dans le cadre sans mesure au montage
 * — le moteur CSS résout `calc(100% - {TOOLTIP_W}px)` contre la largeur réelle
 * de la rangée, ce qu'aucun calcul JS ne peut faire avant le rendu. `hovered.y`
 * est déjà en px réels (la hauteur du SVG est fixée), donc utilisé tel quel.
 *
 * Les deux bornes se plancherent l'une l'autre : `clamp(MIN, VAL, MAX)` vaut
 * `max(MIN, min(VAL, MAX))`, donc CSS retient **MIN** dès que MAX passe dessous
 * — sur une rangée plus étroite que l'infobulle (iPhone SE : ~208px utiles pour
 * 210px de boîte), `calc(100% - 210px)` devient négatif et l'infobulle se
 * plaquait à gauche *en débordant à droite*. D'où `max(0px, …)` sur la borne
 * haute, et une largeur qui suit la rangée quand elle rétrécit.
 */
function Tooltip({ hovered }: { hovered: Hovered }) {
  const scratch = hovered.role === "scratch";
  const position = scratch ? hovered.step.scratch_position : hovered.step.segment_position;
  const xPct = (hovered.x / WIDTH) * 100;
  const y = Math.max(0, hovered.y - TOOLTIP_H - 8);

  return (
    <div
      role="tooltip"
      style={{
        position: "absolute",
        left: `clamp(0px, calc(${xPct}% + 12px), max(0px, calc(100% - ${TOOLTIP_W}px)))`,
        top: y,
        width: `min(${TOOLTIP_W}px, 100%)`,
        height: TOOLTIP_H,
        boxSizing: "border-box",
        borderRadius: 8,
        background: "var(--tcn-ink)",
        opacity: 0.95,
        pointerEvents: "none",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 4,
        padding: "0 12px",
      }}
    >
      <span style={{ fontSize: 12, fontWeight: 700, color: "#fff" }}>{hovered.label}</span>
      <span style={{ fontSize: 12, color: "rgba(255,255,255,.8)" }}>
        {scratch ? "Classement scratch" : "Sur le segment"} : {position}
      </span>
    </div>
  );
}

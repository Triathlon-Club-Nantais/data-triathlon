import { scaleLinear } from "d3-scale";
import { line as d3Line, curveLinear } from "d3-shape";
import type { ProgressionPoint } from "@/lib/utils/ranking";
import { formatDate } from "@/lib/utils/date";
import { pctFr } from "@/lib/utils/format";
import { EmptyState } from "@/components/ui/empty-state";

/** Ce que la courbe mesure : l'échelle, les libellés et les textes de l'état vide. */
export interface ProgressionAxis {
  /** Plafond du bas de l'axe : la marge ajoutée au pire point ne le dépasse pas. */
  max: number;
  /** Plus petit pas de graduation : sous lui, deux graduations porteraient le même libellé. */
  step: number;
  tick(value: number): string;
  label(value: number): string;
  spoken(value: number): string;
  caption: string;
  ariaLabel: string;
  emptyTitle: string;
  emptyDescription: string;
}

export const PERCENT_AXIS: ProgressionAxis = {
  max: 100,
  step: 1,
  tick: (value) => pctFr(value, 0),
  label: (value) => `Top ${pctFr(value, 0)}`,
  spoken: (value) => `top ${value} pour cent`,
  caption: "Classement au sein du peloton à chaque épreuve — plus haut, meilleur.",
  ariaLabel: "Évolution du classement au sein du peloton (plus petit, meilleur)",
  emptyTitle: "Pas encore assez d'épreuves",
  emptyDescription: "Trois épreuves classées sont nécessaires pour tracer une progression — encore un peu de patience.",
};

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

// Nombre de graduations demandé à d3, qui l'ajuste pour garder un pas rond.
const TICKS = 3;

// Sous ce seuil, une tendance ne se lit pas — deux points relient toujours
// une droite, trois sont le minimum pour distinguer une évolution d'un bruit.
const MIN_POINTS = 3;

const JOUR_MS = 86_400_000;
const MOIS_SAISON = ["sept.", "oct.", "nov.", "déc.", "janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août"];
const JOURS_SAISON = 366;

/** Position horizontale (0 à W) d'une date dans sa propre saison, du 1er septembre au 31 août. */
function xOfDate(date: string): number {
  const [annee, mois, jour] = date.split("-").map(Number);
  const debut = Date.UTC(mois >= 9 ? annee : annee - 1, 8, 1);
  return (Math.min(JOURS_SAISON, (Date.UTC(annee, mois - 1, jour) - debut) / JOUR_MS) / JOURS_SAISON) * W;
}

/**
 * Boîte du libellé d'un point, en pourcentage de la rangée : centrée sur son
 * point, mais rabattue dans la rangée aux deux extrémités. Centrée, la dernière
 * dépassait d'une demi-colonne à droite et faisait défiler toute la fiche
 * athlète (#1139). Rabattues, les boîtes d'extrémité se limitent à la place
 * laissée avant leur voisine centrée, l'ellipse tronque le reste. `count` vaut
 * au moins `MIN_POINTS`.
 */
function labelBox(index: number, count: number) {
  const width = 100 / count;
  const center = (100 * index) / (count - 1);
  if (index === 0 || index === count - 1) {
    const endWidth = Math.min(width, 100 / (count - 1) - width / 2);
    return index === 0
      ? ({ left: "0%", width: `${endWidth}%`, textAlign: "left" } as const)
      : ({ left: `${100 - endWidth}%`, width: `${endWidth}%`, textAlign: "right" } as const);
  }
  return { left: `${center - width / 2}%`, width: `${width}%`, textAlign: "center" } as const;
}

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
export function ProgressionChart({ points, comparaison, nonFiables = 0, axis = PERCENT_AXIS }: { points: ProgressionPoint[]; comparaison?: ProgressionPoint[]; nonFiables?: number; axis?: ProgressionAxis }) {
  if (points.length < MIN_POINTS) {
    return (
      <EmptyState
        bare
        className="px-0 py-8"
        title={axis.emptyTitle}
        description={axis.emptyDescription}
      />
    );
  }

  // Une série de comparaison d'un seul point ne trace aucun segment.
  const autre = comparaison && comparaison.length >= 2 ? comparaison : null;
  const percents = [...points, ...(autre ?? [])].map((p) => p.value);
  const best = Math.min(...percents);
  const worst = Math.max(...percents);
  // Au moins un pas de chaque côté : le domaine couvre alors deux multiples du
  // pas, donc deux graduations au moins.
  const margin = Math.max(axis.step, Math.round((worst - best) * 0.15));
  const top = Math.max(0, best - margin);
  // `percent` ne dépasse jamais 100 (`rankRatio` refuse rank > total) : sans
  // ce plafond, un dernier de course affiche une graduation « 114 % » (#677,
  // revue de code — la marge ajoutée à `worst` n'était bornée que d'un côté).
  const bottom = Math.min(axis.max, worst + margin);

  const yScale = scaleLinear().domain([top, bottom]).range([TOP, BOTTOM]);
  const xOf = (index: number) => (points.length === 1 ? W / 2 : (W / (points.length - 1)) * index);

  // Avec une comparaison, les deux séries partagent l'axe septembre à août de
  // leur saison : un jour du calendrier tombe au même x dans l'une et l'autre.
  const parDate = comparaison !== undefined;
  const xPoint = (p: ProgressionPoint, index: number) => (parDate ? xOfDate(p.eventDate) : xOf(index));
  const tracer = (serie: ProgressionPoint[]) =>
    d3Line<{ x: number; y: number }>()
      .x((point) => point.x)
      .y((point) => point.y)
      .curve(curveLinear)(serie.map((p, index) => ({ x: xPoint(p, index), y: yScale(p.value) }))) ?? "";
  const linePoints = points.map((p, index) => ({ x: xPoint(p, index), y: yScale(p.value) }));
  // Tracé droit, pas lissé (#677) : avec 3 à quelques points seulement, une
  // courbe lissée (l'ancien `curveMonotoneX`) dessine un creux ou un sommet
  // qui n'existe pas dans les données — un artefact de la spline, pas une
  // tendance réelle.
  const line =
    d3Line<{ x: number; y: number }>()
      .x((point) => point.x)
      .y((point) => point.y)
      .curve(curveLinear)(linePoints) ?? "";

  // Graduations : sans elles, la courbe montrait un sens de variation sans
  // jamais dire de quelle valeur à quelle valeur (#677). d3 les pose à pas
  // régulier sur des valeurs rondes (#1789), le filtre écarte celles qui
  // tombent sous le pas de l'axe (12,5 % pour un pas de 1 %).
  const ticks = yScale.ticks(TICKS).filter((value) => value % axis.step === 0);

  const resume = (serie: ProgressionPoint[]) => serie.map((p) => `${formatDate(p.eventDate)} ${axis.spoken(p.value)}`).join(", ");
  const absentes = nonFiables > 0 ? `. ${nonFiables} ${nonFiables > 1 ? "épreuves non fiables absentes" : "épreuve non fiable absente"} de la courbe` : "";
  const summary = (autre ? `Cette saison : ${resume(points)}. Saison précédente : ${resume(autre)}` : resume(points)) + absentes;

  return (
    <div>
      <p style={{ marginBottom: 12, fontSize: 13, color: "var(--tcn-text-faint)" }}>
        {axis.caption}
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
            {axis.tick(percent)}
          </span>
        ))}

        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          style={{ width: "100%", height: H, display: "block" }}
          role="img"
          aria-label={`${axis.ariaLabel} : ${summary}.`}
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
          {autre && (
            <path d={tracer(autre)} fill="none" stroke="var(--tcn-text-faint)" strokeWidth={2} strokeDasharray="6 5" vectorEffect="non-scaling-stroke" />
          )}
        </svg>

        {/* Points de la courbe, en HTML : un <circle> dans un viewBox étiré non
            uniformément rendrait une ellipse (même défaut déjà corrigé sur
            `RankingEvolutionChart`, #480, fix B). Rangée dédiée dont la largeur
            épouse celle du SVG, condition pour qu'un pourcentage de `left` se
            résolve juste. */}
        <div style={{ position: "absolute", left: LEFT_GUTTER, right: 0, top: 0, height: H, pointerEvents: "none" }}>
          {points.map((p, index) => (
            <span
              key={p.id}
              data-point={p.id}
              aria-hidden
              style={{
                position: "absolute",
                left: `calc(${(xPoint(p, index) / W) * 100}% - 5px)`,
                top: yScale(p.value) - 5,
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
          {parDate &&
            MOIS_SAISON.map((libelle, mois) => (
              <span
                key={libelle}
                aria-hidden
                style={{
                  position: "absolute",
                  left: `${(xOfDate(`${mois < 4 ? 2001 : 2002}-${String(((8 + mois) % 12) + 1).padStart(2, "0")}-01`) / W) * 100}%`,
                  width: `${100 / 12}%`,
                  overflow: "hidden",
                  whiteSpace: "nowrap",
                  fontSize: 11,
                  lineHeight: "14px",
                  color: "var(--tcn-text-faint)",
                }}
              >
                {libelle}
              </span>
            ))}
          {!parDate && points.map((p, index) => (
            <span
              key={p.id}
              aria-hidden
              style={{
                position: "absolute",
                ...labelBox(index, points.length),
                fontSize: 11,
                lineHeight: "14px",
                color: "var(--tcn-text-faint)",
                fontFamily: "var(--tcn-font-body)",
                whiteSpace: "nowrap",
              }}
            >
              {/* `overflow: hidden` + ellipse sur chaque ligne, jamais sur la
                  rangée : au-delà d'une poignée de points la boîte
                  (`100% / N`) devient plus étroite que le texte, et sans
                  cette protection il déborde dans les colonnes voisines —
                  exactement le défaut déjà qualifié de bloquant sur
                  `RankingEvolutionChart` (#480, RESP-2, revue UI/UX). */}
              <span
                style={{
                  display: "block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {formatDate(p.eventDate)}
              </span>
              <b
                style={{
                  display: "block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  fontSize: 12,
                  lineHeight: "15px",
                  color: "var(--tcn-ink)",
                }}
              >
                {axis.label(p.value)}
              </b>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * Carte résultat à partager (#1371) : la seule ligne de l'adhérent, rendue en
 * PNG dans le navigateur.
 *
 * Trois temps séparés pour pouvoir passer le dessin côté serveur (`next/og`) si
 * les appareils des adhérents s'avèrent trop lents : le modèle (données pures),
 * le dessin (un contexte 2D quelconque), le téléchargement (navigateur seul).
 */
import { CLUB_NAME } from "@/lib/club";
import { eventTypeLabel } from "@/lib/constants";
import { participationStatusLabel } from "@/lib/labels";
import type { Participation } from "@/lib/types";
import { ordinalFr } from "@/lib/utils/format";
import { isNonFinisher } from "@/lib/utils/raceOrder";

export const CARD_WIDTH = 1080;
export const CARD_HEIGHT = 1350;

export interface ResultCardModel {
  club: string;
  event: string;
  date: string;
  discipline: string;
  athlete: string;
  /** Le temps, ou le statut d'un non-finisher (« Abandon »). */
  result: string;
  ranks: string[];
}

/** Ce que la carte dit : rien au delà de la ligne de l'adhérent, aucun tiers. */
export function resultCardModel(participation: Participation): ResultCardModel {
  const { athlete, course } = participation;
  const statut = (participation.status ?? "").toUpperCase();
  const abandon = isNonFinisher(statut);
  const ranks: string[] = [];
  if (!abandon && participation.rank_overall) ranks.push(`${ordinalFr(participation.rank_overall)} au scratch`);
  if (!abandon && participation.rank_category && participation.category) {
    ranks.push(`${ordinalFr(participation.rank_category)} en catégorie ${participation.category}`);
  }
  return {
    club: CLUB_NAME,
    event: course.name,
    date: longDate(course.event_date),
    discipline: eventTypeLabel(course.event_type),
    athlete: [athlete.prenom, athlete.nom].filter(Boolean).join(" "),
    result: abandon
      ? participationStatusLabel(statut as "DNF" | "DNS" | "DSQ")
      : participation.total_time ?? "",
    ranks,
  };
}

function longDate(iso: string | null): string {
  const m = iso?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return "";
  return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export interface CardFonts {
  display: string;
  body: string;
}

const MARGE = 96;

/** Dessine la carte sur `ctx`, supposé de `CARD_WIDTH` × `CARD_HEIGHT`. */
export function drawResultCard(ctx: CanvasRenderingContext2D, model: ResultCardModel, fonts: CardFonts): void {
  // `--tcn-orange-grad` : le dégradé de marque qui porte du texte blanc (#299).
  const fond = ctx.createLinearGradient(0, 0, CARD_WIDTH, CARD_HEIGHT);
  fond.addColorStop(0, "#d64000");
  fond.addColorStop(1, "#b83a00");
  ctx.fillStyle = fond;
  ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
  ctx.fillStyle = "#ffffff";
  ctx.textBaseline = "alphabetic";

  const ligne = (texte: string, taille: number, police: string, y: number) => {
    ctx.font = `${taille}px ${police}`;
    ctx.fillText(texte, MARGE, y, CARD_WIDTH - 2 * MARGE);
  };

  ligne(model.club.toUpperCase(), 40, `600 ${fonts.body}`, 170);
  ligne(model.event, 76, fonts.display, 330);
  ligne([model.discipline, model.date].filter(Boolean).join(" · "), 44, fonts.body, 410);
  ligne(model.athlete, 96, fonts.display, 700);
  ligne(model.result, 200, fonts.display, 940);
  model.ranks.forEach((rang, i) => ligne(rang, 56, `600 ${fonts.body}`, 1090 + i * 80));
}

/** Rend la carte dans un canvas hors DOM et la télécharge en PNG. */
export async function downloadResultCard(model: ResultCardModel, fileName: string): Promise<void> {
  const canvas = document.createElement("canvas");
  canvas.width = CARD_WIDTH;
  canvas.height = CARD_HEIGHT;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Le navigateur ne sait pas dessiner l'image.");
  // Les polices de la page (`next/font`), chargées avant de dessiner.
  const style = getComputedStyle(document.body);
  const fonts = {
    display: style.getPropertyValue("--font-anton").trim() || "sans-serif",
    body: style.getPropertyValue("--font-barlow").trim() || "sans-serif",
  };
  await document.fonts?.ready;
  drawResultCard(ctx, model, fonts);
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error("L'image n'a pas pu être produite.");
  const url = URL.createObjectURL(blob);
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = fileName;
  lien.click();
  URL.revokeObjectURL(url);
}

// Décide quelles tuiles de KPI le profil d'un athlète peut honnêtement rendre.
// Fonction pure et testable — la page ne fait que rendre ce qu'elle reçoit.
import type { Participation } from "@/lib/types";
import { formatToken, ordinalFr } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";

/**
 * Sous ce nombre d'épreuves validées, la grille de cinq tuiles ne dit plus
 * rien : « Meilleure place » et « Top 10 » y répètent l'unique course, et
 * « Meilleur ratio » comme « Format favori » retombent sur un tiret nu. 164 des
 * 350 membres — 47 % — sont dans ce cas (#488, PROF-4).
 */
export const SEUIL_TUILES_COMPLETES = 3;

export interface TuileResume {
  label: string;
  /** Volontairement court : `StatCard` rend `value` en 68 px display sans clamp. */
  value: string;
  hint: string | null;
  /**
   * Taille de police custom pour `value` (`StatCard` la passe en `style`).
   * `.tcn-stat-value` ne porte pas de `clamp()` — ciblé sur la tuile
   * « Temps » : "01:02:03" en 68px (223px, insécable) déborde la piste de
   * 133px qu'ouvre `sm:grid-cols-3` entre 640px et ~926px (#488, revue
   * UI/UX). 40px pour 8 glyphes tient dans cette piste.
   */
  valueFontSize?: number;
}

export interface ResumeAthlete {
  /**
   * `complet` : les cinq tuiles habituelles. `reduit` : ce qui est certain de
   * la dernière épreuve. `vide` : rien de validé, donc aucune tuile.
   */
  regime: "complet" | "reduit" | "vide";
  validees: Participation[];
  enAttente: number;
  /**
   * La dernière participation validée (départage à date égale : la dernière
   * du tableau — voir `derniere()`). `null` en régime `vide`. Seule source de
   * vérité pour « la dernière épreuve » : la page ne doit pas la recalculer
   * (#488, revue finale — deux règles de départage divergentes y avaient
   * laissé la pastille Catégorie de l'en-tête décrire une autre course que
   * les tuiles Discipline/Temps juste en dessous).
   */
  derniere: Participation | null;
  /** Tuiles du régime `reduit` uniquement — vide dans les deux autres. */
  tuiles: TuileResume[];
}

/** La plus récente par date d'épreuve ; à date égale ou absente, la dernière reçue. */
function derniere(parts: Participation[]): Participation | null {
  let best: Participation | null = null;
  for (const p of parts) {
    if (best === null || (p.course.event_date ?? "") >= (best.course.event_date ?? "")) best = p;
  }
  return best;
}

export function resumeAthlete(participations: Participation[]): ResumeAthlete {
  // Même filtre que les KPI depuis #438 : une saisie manuelle en attente de
  // validation ne doit pas peser sur les chiffres avant vérification.
  const validees = participations.filter((p) => !p.is_pending_validation);
  const enAttente = participations.length - validees.length;
  const derniereValidee = derniere(validees);

  if (validees.length === 0) {
    return { regime: "vide", validees, enAttente, derniere: null, tuiles: [] };
  }
  if (validees.length >= SEUIL_TUILES_COMPLETES) {
    return { regime: "complet", validees, enAttente, derniere: derniereValidee, tuiles: [] };
  }

  const p = derniereValidee as Participation;
  const date = formatDate(p.course.event_date) || null;
  const tuiles: TuileResume[] = [
    {
      label: "Épreuves",
      value: String(validees.length),
      hint: enAttente > 0 ? `${enAttente} en attente de validation` : null,
    },
  ];

  // `formatToken` retombe sur « — » quand il ne reconnaît rien : dans ce cas la
  // tuile disparaît au lieu d'afficher un tiret nu, ce que PROF-4 interdit.
  const discipline = formatToken(p.course.event_type, p.course.distance_km);
  if (discipline !== "—") {
    tuiles.push({ label: "Discipline", value: discipline, hint: p.course.name });
  }

  if (p.total_time) {
    tuiles.push({ label: "Temps", value: p.total_time, hint: date, valueFontSize: 40 });
  } else if (p.rank_overall != null && p.rank_overall >= 1) {
    // Repli sur la place, qui reste un fait de cette course-là — et non une
    // « meilleure place » qui ne compare rien.
    tuiles.push({
      label: "Place",
      value: ordinalFr(p.rank_overall),
      hint: p.course_finishers ? `sur ${p.course_finishers} classés` : date,
    });
  }

  return { regime: "reduit", validees, enAttente, derniere: p, tuiles };
}

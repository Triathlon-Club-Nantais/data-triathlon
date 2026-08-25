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
}

export interface ResumeAthlete {
  /**
   * `complet` : les cinq tuiles habituelles. `reduit` : ce qui est certain de
   * la dernière épreuve. `vide` : rien de validé, donc aucune tuile.
   */
  regime: "complet" | "reduit" | "vide";
  validees: Participation[];
  enAttente: number;
  /** Tuiles du régime `reduit` uniquement — vide dans les deux autres. */
  tuiles: TuileResume[];
}

/** La plus récente par date d'épreuve ; à date égale ou absente, la dernière reçue. */
function derniere(parts: Participation[]): Participation {
  let best = parts[0];
  for (const p of parts) {
    if ((p.course?.event_date ?? "") >= (best.course?.event_date ?? "")) best = p;
  }
  return best;
}

export function resumeAthlete(participations: Participation[]): ResumeAthlete {
  // Même filtre que les KPI depuis #438 : une saisie manuelle en attente de
  // validation ne doit pas peser sur les chiffres avant vérification.
  const validees = participations.filter((p) => !p.is_pending_validation);
  const enAttente = participations.length - validees.length;

  if (validees.length === 0) return { regime: "vide", validees, enAttente, tuiles: [] };
  if (validees.length >= SEUIL_TUILES_COMPLETES) {
    return { regime: "complet", validees, enAttente, tuiles: [] };
  }

  const p = derniere(validees);
  const date = formatDate(p.course?.event_date) || null;
  const tuiles: TuileResume[] = [
    {
      label: "Épreuves",
      value: String(validees.length),
      hint: enAttente > 0 ? `${enAttente} en attente de validation` : null,
    },
  ];

  // `formatToken` retombe sur « — » quand il ne reconnaît rien : dans ce cas la
  // tuile disparaît au lieu d'afficher un tiret nu, ce que PROF-4 interdit.
  const discipline = formatToken(p.course?.event_type, p.course?.distance_km);
  if (discipline !== "—") {
    tuiles.push({ label: "Discipline", value: discipline, hint: p.course?.name ?? null });
  }

  if (p.total_time) {
    tuiles.push({ label: "Temps", value: p.total_time, hint: date });
  } else if (p.rank_overall != null && p.rank_overall >= 1) {
    // Repli sur la place, qui reste un fait de cette course-là — et non une
    // « meilleure place » qui ne compare rien.
    tuiles.push({
      label: "Place",
      value: ordinalFr(p.rank_overall),
      hint: p.course_finishers ? `sur ${p.course_finishers} classés` : date,
    });
  }

  return { regime: "reduit", validees, enAttente, tuiles };
}

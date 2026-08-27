// Comparaison de deux athlètes sur leurs épreuves communes. Fonction pure et
// testable — la donnée (participations des deux athlètes) est déjà en mémoire
// côté client (US6, #466), aucun nouvel appel API n'est nécessaire ici.
import type { Participation } from "@/lib/types";
import { parseTotalTimeSeconds } from "@/lib/utils/histogram-ticks";

export interface CommonParticipation {
  courseId: number;
  courseName: string;
  eventDate: string | null;
  mine: Participation;
  theirs: Participation;
  mineSeconds: number | null;
  theirsSeconds: number | null;
}

/**
 * Épreuves courues par les deux athlètes, appariées par `course.id`.
 * Triées par date croissante ; les épreuves sans date connue passent en fin.
 */
export function commonParticipations(mine: Participation[], theirs: Participation[]): CommonParticipation[] {
  const theirsByCourse = new Map<number, Participation>();
  for (const p of theirs) {
    theirsByCourse.set(p.course.id, p);
  }

  const result: CommonParticipation[] = [];
  for (const p of mine) {
    const match = theirsByCourse.get(p.course.id);
    if (!match) continue;
    result.push({
      courseId: p.course.id,
      courseName: p.course.name,
      eventDate: p.course.event_date,
      mine: p,
      theirs: match,
      mineSeconds: parseTotalTimeSeconds(p.total_time),
      theirsSeconds: parseTotalTimeSeconds(match.total_time),
    });
  }

  return result.sort((a, b) => (a.eventDate ?? "9999").localeCompare(b.eventDate ?? "9999"));
}

/** Durée compacte et lisible : « 1 h 05 min », « 3 min 25 s », « 45 s ». */
function formatDurationCompact(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = Math.floor(totalSeconds % 60);
  if (h > 0) return `${h} h ${String(m).padStart(2, "0")} min`;
  if (m > 0) return `${m} min ${String(s).padStart(2, "0")} s`;
  return `${s} s`;
}

/**
 * Écart chiffré entre mon temps et celui du coéquipier comparé (#689) —
 * l'information réellement recherchée par l'utilisateur, jusque-là déductible
 * uniquement en comparant deux longueurs de barre à l'œil. « Retard » /
 * « avance » dit le sens sans dépendre d'un signe +/- que rien n'explique à
 * l'écran.
 */
export function formatDelta(mineSeconds: number, theirsSeconds: number): string {
  const diff = mineSeconds - theirsSeconds;
  if (diff === 0) return "Temps identique";
  const duration = formatDurationCompact(Math.abs(diff));
  return diff > 0 ? `${duration} de retard` : `${duration} d'avance`;
}

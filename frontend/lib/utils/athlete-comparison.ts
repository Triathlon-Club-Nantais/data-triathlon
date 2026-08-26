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

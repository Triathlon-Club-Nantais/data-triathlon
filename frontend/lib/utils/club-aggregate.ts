import type { Participation } from "@/lib/types";

/** Participations les plus récentes (par date d'épreuve puis ajout). */
export function recentParticipations(
  parts: Participation[],
  limit = 8,
): Participation[] {
  return [...parts]
    .sort((a, b) => {
      const da = a.course.event_date ?? "";
      const db = b.course.event_date ?? "";
      if (da !== db) return db.localeCompare(da);
      return (b.created_at ?? "").localeCompare(a.created_at ?? "");
    })
    .slice(0, limit);
}

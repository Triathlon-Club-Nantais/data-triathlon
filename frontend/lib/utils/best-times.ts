import { eventTypeLabel } from "@/lib/constants";
import type { Participation } from "@/lib/types";
import { disciplineOf, formatToken } from "@/lib/utils/format";
import { isNonFinisher } from "@/lib/utils/raceOrder";
import { estRelais } from "@/lib/utils/relais";
import { secondsFromHms } from "@/lib/utils/time";

export interface BestTime {
  discipline: string;
  format: string;
  seconds: number;
  participation: Participation;
}

/**
 * Meilleur temps par couple (discipline, format) : la discipline fait partie de
 * la clé, `formatToken` rendant « M » pour un triathlon comme pour un duathlon.
 * Mêmes exclusions que les tuiles (#438, #894, #115). Un meilleur temps sur M,
 * jamais un record : deux M n'ont pas forcément le même parcours (#1361).
 */
export function bestTimes(participations: Participation[]): BestTime[] {
  const best = new Map<string, BestTime>();
  for (const participation of participations) {
    if (participation.is_pending_validation || estRelais(participation)) continue;
    if (participation.course.is_reliable === false || isNonFinisher(participation.status)) continue;
    const seconds = secondsFromHms(participation.total_time);
    const format = formatToken(participation.course.event_type, participation.course.distance_km);
    if (seconds == null || format === "—") continue;
    const discipline = disciplineOf(participation.course.event_type);
    const key = `${discipline}|${format}`;
    const current = best.get(key);
    if (!current || seconds < current.seconds) best.set(key, { discipline, format, seconds, participation });
  }
  return [...best.values()].sort(
    (a, b) =>
      eventTypeLabel(a.discipline).localeCompare(eventTypeLabel(b.discipline), "fr") || a.seconds - b.seconds,
  );
}

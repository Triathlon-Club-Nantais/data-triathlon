import { eventTypeLabel } from "@/lib/constants";
import type { Participation } from "@/lib/types";
import { disciplineOf, formatToken } from "@/lib/utils/format";
import { isNonFinisher } from "@/lib/utils/raceOrder";
import { estRelais } from "@/lib/utils/relais";
import { comparableSeconds } from "@/lib/utils/time";

// Seuls une taille ou une distance nomment un format. Les replis de
// `formatToken` (« CAP », « TR », « CYC »…) mêleraient un 5 km et un marathon.
const COMPARABLE_FORMAT = /^(XS|S|M|L|XL|\d+km)$/;

export interface BestTime {
  discipline: string;
  format: string;
  seconds: number;
  participation: Participation;
}

/** Résultat qui vaut performance : ni en attente, ni relais, ni épreuve douteuse, ni abandon. */
export function countsAsPerformance(participation: Participation): boolean {
  return (
    !participation.is_pending_validation &&
    !estRelais(participation) &&
    participation.course.is_reliable !== false &&
    !isNonFinisher(participation.status)
  );
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
    if (!countsAsPerformance(participation)) continue;
    const seconds = comparableSeconds(participation.total_time);
    const format = formatToken(participation.course.event_type, participation.course.distance_km);
    const discipline = disciplineOf(participation.course.event_type);
    if (seconds == null || !discipline || !COMPARABLE_FORMAT.test(format)) continue;
    const key = `${discipline}|${format}`;
    const current = best.get(key);
    const faster =
      !current ||
      seconds < current.seconds ||
      (seconds === current.seconds && isEarlier(participation, current.participation));
    if (faster) {
      best.set(key, { discipline, format, seconds, participation });
    }
  }
  return [...best.values()].sort(
    (a, b) =>
      eventTypeLabel(a.discipline).localeCompare(eventTypeLabel(b.discipline), "fr") || a.seconds - b.seconds,
  );
}

/** À temps égal, la première épreuve courue garde la ligne. */
function isEarlier(candidate: Participation, current: Participation): boolean {
  return (candidate.course.event_date ?? "") < (current.course.event_date ?? "");
}

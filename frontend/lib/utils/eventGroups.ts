import type { EventOut } from "@/lib/types";

/** Épreuves d'une même compétition parente, dans l'ordre où la liste les sert. */
export interface EventGroup {
  prefix: string;
  events: EventOut[];
  total: number;
  tcnCount: number;
}

/** Compétition parente d'une épreuve : ce qui précède le premier « - ». */
function competitionOf(name: string): string {
  const cut = name.indexOf(" - ");
  return cut === -1 ? name : name.slice(0, cut);
}

/**
 * Regroupe les épreuves **contiguës** partageant leur compétition parente.
 *
 * Contiguës, et pas « toutes celles du même préfixe » : l'ordre servi par
 * l'API est la source de vérité de l'écran (date, ou nom). Rapprocher deux
 * séries séparées déplacerait des lignes hors de leur position triée, et le
 * défilement infini ferait sauter une ligne déjà lue vers le haut à chaque
 * page chargée. Les épreuves d'une même compétition partagent leur date et
 * leur préfixe : elles sont adjacentes dans les trois tris de l'écran.
 */
export function groupEventsByCompetition(events: EventOut[]): EventGroup[] {
  const groups: EventGroup[] = [];
  for (const event of events) {
    const prefix = competitionOf(event.event_name);
    const last = groups[groups.length - 1];
    if (last && last.prefix === prefix) {
      last.events.push(event);
      last.total += event.total;
      last.tcnCount += event.tcn_count;
    } else {
      groups.push({ prefix, events: [event], total: event.total, tcnCount: event.tcn_count });
    }
  }
  return groups;
}

/** Part distinctive d'une épreuve, une fois son préfixe porté par le groupe. */
export function eventSuffix(name: string, prefix: string): string {
  return name.startsWith(`${prefix} - `) ? name.slice(prefix.length + 3) : name;
}

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
 * page chargée. Ça vaut aussi pour l'ordre par similarité, qui casse déjà
 * la contiguïté (#567, backend — rien à changer ici une fois corrigé).
 *
 * La clé de groupe est le préfixe **et** la date, à égalité stricte (#568,
 * cas 1) — équivalent à `` `${prefix}||${event_date}` ``, comparé ici
 * membre à membre plutôt que concaténé. Sans la date, deux éditions du même
 * nom se confondaient sous le tri « Nom »
 * (`ORDER BY courses.name ASC, courses.event_date DESC` : deux années
 * adjacentes par construction) — la ligne de groupe affichait la date de la
 * première tout en sommant les compteurs des deux. Égalité stricte, assumée :
 * un triathlon le samedi et son duathlon le dimanche, même préfixe, cessent
 * de se regrouper. On assouplira sur constat
 * (`course_duplicates._dates_are_close` porte déjà une notion de proximité
 * de dates si le besoin se confirme), pas par anticipation.
 *
 * `event_date` peut être `null` (mise à vide légitime, `lib/types.ts`) ;
 * `===` le traite comme une valeur comme une autre, donc deux épreuves sans
 * date et de même préfixe se regroupent toujours entre elles (comportement
 * choisi ici), et une épreuve **datée** ne fusionne jamais avec une non
 * datée du même préfixe.
 */
export function groupEventsByCompetition(events: EventOut[]): EventGroup[] {
  const groups: EventGroup[] = [];
  for (const event of events) {
    const prefix = competitionOf(event.event_name);
    const last = groups[groups.length - 1];
    if (last && last.prefix === prefix && last.events[0].event_date === event.event_date) {
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

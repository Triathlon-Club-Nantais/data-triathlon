import type { EventOut } from "@/lib/types";

/** Nom d'épreuve affiché, suffixé « (Relais) » quand la course est un relais. */
export function formatEventName(name: string, isRelay: boolean): string {
  return isRelay ? `${name} (Relais)` : name;
}

/**
 * Trie une liste d'épreuves par date décroissante (#483, NAV-7) — la page
 * d'atterrissage doit répondre à « qu'est-ce qui vient de se passer », pas
 * « que fait-on le plus souvent ». `event_date` est nullable
 * (`lib/types.ts`) : une épreuve sans date est reléguée en fin de liste,
 * jamais devant une épreuve datée. Ne mute pas son argument.
 */
export function sortEventsByDateDesc(events: EventOut[]): EventOut[] {
  return [...events].sort((a, b) => {
    if (!a.event_date && !b.event_date) return 0;
    if (!a.event_date) return 1;
    if (!b.event_date) return -1;
    return b.event_date.localeCompare(a.event_date);
  });
}

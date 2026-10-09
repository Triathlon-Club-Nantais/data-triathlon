import type { EventOut } from "@/lib/types";

/** Nom d'épreuve affiché, suffixé « (Relais) » quand la course est un relais. */
export function formatEventName(name: string, isRelay: boolean): string {
  return isRelay ? `${name} (Relais)` : name;
}

/**
 * Ce qu'affiche une liste à la place du compte d'une épreuve qui n'a que des
 * résultats en attente de validation (#1273), sinon `null` : une épreuve qui
 * a des résultats validés garde son compte, sans mention.
 */
export function pendingOnlyLabel(total: number, pendingCount: number | undefined): string | null {
  if (total > 0 || !pendingCount) return null;
  return `${pendingCount} résultat${pendingCount > 1 ? "s" : ""} en attente`;
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

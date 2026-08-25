import Link from "next/link";
import { eventTypeLabel } from "@/lib/constants";
import { CLUB_NAME_SHORT } from "@/lib/club";
import { formatMonth } from "@/lib/utils/date";
import type { GeoEvent } from "@/lib/types";

/**
 * La carte, en texte.
 *
 * Les chiffres d'une épreuve ne vivaient que dans un `<Popup>` accroché à un
 * `CircleMarker`, et Leaflet ne rend focusables que les `L.Marker` — jamais les
 * couches vectorielles. Zéro pour cent du contenu de la carte était donc
 * atteignable au clavier (WCAG 2.1.1). Cette liste porte la même information,
 * et dit **en mots** ce que le remplissage des cercles disait par la seule
 * couleur (WCAG 1.4.1).
 *
 * Repliée par défaut : c'est un équivalent, pas un doublon à lire d'abord — mais
 * `<details>`/`<summary>` la rend atteignable au clavier sans script.
 */
export function ListeEpreuves({ events }: { events: GeoEvent[] }) {
  if (events.length === 0) return null;

  return (
    <details className="rounded-[var(--tcn-radius-xl)] border border-[var(--tcn-border)] bg-[var(--tcn-surface)] px-4 py-3">
      <summary className="tcn-rowlink text-sm font-semibold text-[var(--tcn-text-body)]">
        Les {events.length} épreuve{events.length > 1 ? "s" : ""} de la carte, en texte
      </summary>
      <table className="mt-3 w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase text-[var(--tcn-text-faint)]">
            <th scope="col" className="py-1 pr-3 font-semibold">Épreuve</th>
            <th scope="col" className="py-1 pr-3 font-semibold">Date</th>
            <th scope="col" className="py-1 pr-3 font-semibold">Participants</th>
            <th scope="col" className="py-1 font-semibold">{CLUB_NAME_SHORT}</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev, i) => (
            <tr key={`${ev.event_name}-${i}`} className="border-t border-[var(--tcn-border-faint)]">
              <th scope="row" className="py-1.5 pr-3 font-medium text-[var(--tcn-text)]">
                <Link href={`/courses/${ev.course_id}`} className="underline">
                  {ev.event_name}
                </Link>
                {ev.event_type ? <span className="text-[var(--tcn-text-faint)]"> · {eventTypeLabel(ev.event_type)}</span> : null}
              </th>
              <td className="py-1.5 pr-3 text-[var(--tcn-text-body)]">
                {ev.event_date ? formatMonth(ev.event_date.slice(0, 7)) : "date inconnue"}
              </td>
              <td className="num py-1.5 pr-3 text-[var(--tcn-text-body)]">
                {ev.count} participant{ev.count > 1 ? "s" : ""}
              </td>
              <td className="py-1.5 text-[var(--tcn-text-body)]">
                {ev.tcn_count > 0
                  ? `${ev.tcn_count} membre${ev.tcn_count > 1 ? "s" : ""}`
                  : "aucun membre"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

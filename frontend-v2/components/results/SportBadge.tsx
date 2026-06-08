import { eventTypeLabel } from "@/lib/constants";
import { eventTypeColor, tintedStyle } from "@/lib/sport-colors";

/**
 * SPLIT — `TypeTag`. Badge teinté selon la famille de discipline (aplat 14 %,
 * libellé `…-ink`), en micro-capitales.
 */
export function SportBadge({ type }: { type: string | null | undefined }) {
  if (!type) return null;
  return (
    <span
      className="micro-label inline-flex w-fit items-center rounded-md px-2 py-[3px] whitespace-nowrap"
      style={tintedStyle(eventTypeColor(type))}
    >
      {eventTypeLabel(type)}
    </span>
  );
}

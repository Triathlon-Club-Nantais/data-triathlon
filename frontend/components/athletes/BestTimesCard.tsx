import { Card, FormatChip, LigneCarte } from "@/components/tcn";
import { eventTypeLabel } from "@/lib/constants";
import type { Participation } from "@/lib/types";
import { bestTimes } from "@/lib/utils/best-times";
import { formatDate } from "@/lib/utils/date";

/** Meilleur temps par discipline et par format (#1361) ; rien sans temps comparable. */
export function BestTimesCard({ participations }: { participations: Participation[] }) {
  const lines = bestTimes(participations);
  if (lines.length === 0) return null;

  return (
    <Card padding={0} style={{ overflow: "hidden" }}>
      <div style={{ padding: "20px 26px 12px" }}>
        <h2
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: 22,
            fontWeight: 400,
            color: "var(--tcn-ink)",
            margin: 0,
          }}
        >
          Meilleurs temps
        </h2>
        <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--tcn-text-faint)" }}>
          Un temps par discipline et par format. Deux épreuves d&apos;un même format n&apos;ont pas
          toujours le même parcours.
        </p>
      </div>
      {lines.map(({ discipline, format, participation }) => (
        <LigneCarte
          key={`${discipline}|${format}`}
          href={`/courses/${participation.course.id}/participations/${participation.id}`}
          // Le format est déjà dit par le préfixe masqué de la valeur.
          marqueur={
            <span aria-hidden="true">
              <FormatChip>{format}</FormatChip>
            </span>
          }
          titre={eventTypeLabel(discipline)}
          meta={[participation.course.name, formatDate(participation.course.event_date)]
            .filter(Boolean)
            .join(", ")}
          valeur={
            <>
              <span className="sr-only">meilleur temps sur {format} : </span>
              {participation.total_time}
            </>
          }
        />
      ))}
    </Card>
  );
}

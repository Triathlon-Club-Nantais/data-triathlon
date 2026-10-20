"use client";

import { useQuery } from "@tanstack/react-query";
import { Badge, Card, FormatChip, LigneCarte } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api/client";
import { eventTypeLabel } from "@/lib/constants";
import { recordsPersonnels } from "@/lib/mon-espace";
import type { Participation } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

const LIBELLE_BADGE = { record: "record perso", premiere: "1re fois" };

/** Records de la sélection face à la carrière entière (toutes saisons, requête propre). */
export function OngletRecords({
  athleteId,
  federalOnly,
  selection,
}: {
  athleteId: number;
  federalOnly: boolean;
  selection: Participation[];
}) {
  const carriere = useQuery({
    queryKey: ["mon-espace", "carriere", athleteId, federalOnly],
    queryFn: () => apiClient.getAthlete(athleteId, { federal_only: federalOnly }),
    retry: false,
  });

  return (
    <Card>
      <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>
        Records
      </h2>
      {carriere.isPending ? (
        <Skeleton className="mt-4 h-16 w-full" />
      ) : carriere.isError ? (
        <p role="alert">{carriere.error.message}</p>
      ) : (
        <Lignes selection={selection} carriere={carriere.data.participations} />
      )}
    </Card>
  );
}

function Lignes({ selection, carriere }: { selection: Participation[]; carriere: Participation[] }) {
  const lignes = recordsPersonnels(selection, carriere);
  if (lignes.length === 0) {
    return <EmptyState bare title="Aucun record sur cette sélection" description="Un temps comparable sur un format de XS à XL ou une distance donne une ligne." />;
  }
  return (
    <div style={{ margin: "12px -26px -20px" }}>
      {lignes.map(({ discipline, format, meilleur, record, badge }) => (
        <LigneCarte
          key={`${discipline}|${format}`}
          href={`/courses/${meilleur.participation.course.id}/participations/${meilleur.participation.id}`}
          marqueur={
            <span aria-hidden="true">
              <FormatChip>{format}</FormatChip>
            </span>
          }
          titre={
            <>
              {eventTypeLabel(discipline)} {format}
              {badge ? (
                <Badge variant="orange" style={{ marginLeft: 8 }}>
                  {LIBELLE_BADGE[badge]}
                </Badge>
              ) : null}
            </>
          }
          meta={[
            meilleur.participation.course.name,
            formatDate(meilleur.participation.course.event_date),
            record.participation.id === meilleur.participation.id ? null : `Record : ${record.temps}`,
          ]
            .filter(Boolean)
            .join(", ")}
          valeur={meilleur.temps}
        />
      ))}
    </div>
  );
}

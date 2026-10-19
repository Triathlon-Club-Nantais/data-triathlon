"use client";

import { useQueries } from "@tanstack/react-query";
import { BarList } from "@/components/charts/BarList";
import { Card } from "@/components/tcn";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api/client";
import { eventTypeLabel } from "@/lib/constants";
import { ecartAuClub, formatDuree, mesMediansDeSplits, repartitionDisciplines, SEGMENTS } from "@/lib/mon-espace";
import { eventTypeColor } from "@/lib/sport-colors";
import type { Participation } from "@/lib/types";
import { serializeSeasons } from "@/lib/utils/season";
import { secondsFromHms } from "@/lib/utils/time";

/** Sous cet effectif de lignes club, la médiane ne dit rien de fiable. */
const ECHANTILLON_MIN = 5;

const titre = { fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 } as const;

/** Onglet Disciplines de Mon espace (#1699) : répartition de mes épreuves, mes splits face à la médiane du club. */
export function OngletDisciplines({
  participations,
  federalOnly,
  seasons,
}: {
  participations: Participation[];
  federalOnly: boolean;
  seasons: number[];
}) {
  const repartition = repartitionDisciplines(participations);
  const miens = mesMediansDeSplits(participations);
  const types = [...miens.keys()];
  const clubs = useQueries({
    queries: types.map((type) => ({
      queryKey: ["mon-espace", "split-medians", type, federalOnly, serializeSeasons(seasons)],
      queryFn: () => apiClient.getClubSplitMedians({ event_type: type, federal_only: federalOnly, seasons }),
      retry: false,
    })),
  });

  const lignes = types.flatMap((type, i) => {
    const club = clubs[i].data;
    if (!club || club.sample < ECHANTILLON_MIN) return [];
    const segments = SEGMENTS.flatMap(({ cle, libelle }) => {
      const reference = secondsFromHms(club[cle]);
      return reference ? [{ libelle, moi: miens.get(type)![cle], reference }] : [];
    });
    return segments.length === SEGMENTS.length ? [{ type, segments }] : [];
  });
  const enCours = clubs.some((c) => c.isPending);

  return (
    <div className="space-y-6">
      <Card>
        <h2 style={titre}>Mes épreuves par discipline</h2>
        <div style={{ marginTop: 12 }}>
          <BarList
            entries={repartition}
            labeller={(cle) => {
              const [discipline, format] = cle.split("|");
              return `${eventTypeLabel(discipline)} ${format}`;
            }}
            colorer={(cle) => eventTypeColor(cle.split("|")[0])}
            subjectLabel="discipline et format"
            emptyTitle="Aucune épreuve sur cette sélection"
          />
        </div>
      </Card>
      {types.length > 0 && (
        <Card>
          <h2 style={titre}>Mes splits face au club</h2>
          {enCours ? (
            <Skeleton className="mt-4 h-16 w-full" />
          ) : lignes.length === 0 ? (
            <EmptyState bare title="Aucune comparaison possible sur cette sélection" description="Il faut des splits fiables et au moins 5 résultats du club sur le même format." />
          ) : (
            lignes.map(({ type, segments }) => (
              <section key={type} style={{ marginTop: 12 }}>
                <h3 style={{ fontWeight: 700, margin: 0 }}>{eventTypeLabel(type)}</h3>
                <ul style={{ listStyle: "none", padding: 0, margin: "6px 0 0" }}>
                  {segments.map(({ libelle, moi, reference }) => (
                    <li key={libelle} style={{ marginTop: 4 }}>
                      {`${libelle}, vous ${formatDuree(moi)}, club ${formatDuree(reference)}, ${ecartAuClub(moi, reference)}`}
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )}
        </Card>
      )}
    </div>
  );
}

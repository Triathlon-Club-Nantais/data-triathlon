"use client";

import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { apiClient } from "@/lib/api/client";
import { chiffresSaison, fenetreSaisonPrecedente } from "@/lib/mon-espace";
import { useHydratedSession } from "@/lib/queries/auth";
import { serializeSeasons } from "@/lib/utils/season";
import { InvitationMonEspace } from "./InvitationMonEspace";
import { MesChiffres } from "./MesChiffres";
import { OngletsMonEspace } from "./OngletsMonEspace";
import { SqueletteMonEspace } from "./SqueletteMonEspace";

/** Grille de Mon espace : la navigation est le rail de l'application, à gauche. */
export function MonEspaceLayout({ centre, droite }: { centre: ReactNode; droite: ReactNode }) {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div data-testid="mon-espace-centre" className="min-w-0 space-y-6">
        {centre}
      </div>
      <aside data-testid="mon-espace-droite" aria-label="En plus" className="min-w-0 space-y-6">
        {droite}
      </aside>
    </div>
  );
}

/** Mon espace du membre dont le compte est rattaché à une fiche (#1695). */
export function MonEspace({ seasons, federalOnly }: { seasons: number[]; federalOnly: boolean }) {
  const session = useHydratedSession();
  const athlete = session.data?.athlete ?? null;
  const filters = { federal_only: federalOnly };

  const courant = useQuery({
    queryKey: ["mon-espace", "chiffres", athlete?.id, serializeSeasons(seasons), federalOnly],
    queryFn: () => apiClient.getAthlete(athlete!.id, { seasons: serializeSeasons(seasons), ...filters }),
    enabled: athlete !== null,
    retry: false,
  });

  // Écart seulement sur une saison : comparer à date égale n'a pas de sens sur plusieurs.
  const saison = seasons.length === 1 ? seasons[0] : null;
  const precedent = useQuery({
    queryKey: ["mon-espace", "precedent", athlete?.id, saison, federalOnly],
    queryFn: async () => {
      const { start, end } = fenetreSaisonPrecedente(saison!, new Date());
      const { participations } = await apiClient.getAthlete(athlete!.id, { seasons: String(saison! - 1), ...filters });
      return chiffresSaison(
        participations.filter((p) => p.course.event_date !== null && p.course.event_date >= start && p.course.event_date <= end),
      );
    },
    enabled: athlete !== null && saison !== null,
    retry: false,
  });

  if (session.data === undefined) {
    return session.error ? <p role="alert">{session.error.message}</p> : <SqueletteMonEspace />;
  }
  if (athlete === null) return <InvitationMonEspace session={session.data} />;
  if (courant.error) return <p role="alert">{courant.error.message}</p>;
  if (courant.isPending) return <SqueletteMonEspace />;

  return (
    <MonEspaceLayout
      centre={
        <>
          <MesChiffres courant={chiffresSaison(courant.data.participations)} precedent={precedent.data ?? null} />
          <OngletsMonEspace
            athleteId={athlete.id}
            athleteName={`${athlete.prenom} ${athlete.nom}`}
            participations={courant.data.participations}
            challenges={courant.data.challenges}
          />
        </>
      }
      droite={null}
    />
  );
}

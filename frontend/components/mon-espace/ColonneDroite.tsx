"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { chiffresSaison, prochainPalier, recordsPersonnels } from "@/lib/mon-espace";
import type { Participation } from "@/lib/types";
import { compteMaSaison } from "@/lib/utils/ma-saison";
import { currentSeason, seasonOf } from "@/lib/utils/season";
import { DernierResultat } from "./DernierResultat";
import { MesDemandes } from "./MesDemandes";
import { MaPlaceAuClub } from "./MaPlaceAuClub";
import { MesCoequipiers } from "./MesCoequipiers";
import { ResultatEquipeManquant } from "./ResultatEquipeManquant";
import { MiniCarte } from "./MiniCarte";
import { ProchainPalier } from "./ProchainPalier";

/** Encarts de droite de Mon espace : dernier résultat, place au club, prochain palier. */
export function ColonneDroite({
  athleteId,
  selection,
  seasons,
  federalOnly,
}: {
  athleteId: number;
  selection: Participation[];
  seasons: number[];
  federalOnly: boolean;
}) {
  // Même requête que l'onglet Records : le cache la partage.
  const carriere = useQuery({
    queryKey: ["mon-espace", "carriere", athleteId, federalOnly],
    queryFn: () => apiClient.getAthlete(athleteId, { federal_only: federalOnly }),
    retry: false,
  });
  const validees = selection.filter((p) => !p.is_pending_validation && p.course.event_date !== null);
  const dernier = validees.reduce<Participation | null>(
    // Même jour : le plus grand id l'emporte, pour un résultat stable.
    (plus, p) => {
      if (plus === null) return p;
      const [a, b] = [p.course.event_date!, plus.course.event_date!];
      return a > b || (a === b && p.id > plus.id) ? p : plus;
    },
    null,
  );
  const toutes = carriere.data?.participations;
  const record =
    dernier !== null && toutes !== undefined && recordsPersonnels(selection, toutes).some((r) => r.badge === "record" && r.meilleur.participation.id === dernier.id);

  // Un palier vise la saison en cours : pas de « prochain » pour une saison close, ni sans carrière.
  let palier = null;
  if (seasons.length === 1 && seasons[0] === currentSeason() && toutes !== undefined) {
    const parSaison = new Map<number, Participation[]>();
    for (const p of toutes) {
      if (p.course.event_date === null) continue;
      const saison = seasonOf(p.course.event_date);
      parSaison.set(saison, [...(parSaison.get(saison) ?? []), p]);
    }
    const { epreuves, podiums } = chiffresSaison(selection);
    palier = prochainPalier({ epreuves, podiums }, [...parSaison.values()].map((s) => compteMaSaison(s, "all")));
  }

  return (
    <>
      <MesDemandes />
      <DernierResultat participation={dernier} record={record} />
      <MaPlaceAuClub athleteId={athleteId} seasons={seasons} federalOnly={federalOnly} />
      <ProchainPalier palier={palier} />
      <MesCoequipiers athleteId={athleteId} seasons={seasons} federalOnly={federalOnly} />
      <ResultatEquipeManquant />
      <MiniCarte courseIds={[...new Set(selection.map((p) => p.course.id))]} />
    </>
  );
}

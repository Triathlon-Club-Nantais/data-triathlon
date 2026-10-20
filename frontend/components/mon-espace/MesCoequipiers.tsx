"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Card, Eyebrow } from "@/components/tcn";
import { apiClient } from "@/lib/api/client";
import { queryKeys } from "@/lib/queries/keys";
import { motCompte } from "@/lib/utils/format";

/** Les membres du club avec qui j'ai le plus couru sur la sélection (#1701). */
export function MesCoequipiers({ athleteId, seasons, federalOnly }: { athleteId: number; seasons: number[]; federalOnly: boolean }) {
  const coequipiers = useQuery({
    queryKey: queryKeys.myTeammates(seasons, federalOnly),
    queryFn: () => apiClient.getMyTeammates({ federal_only: federalOnly, seasons }),
    retry: false,
  });

  if (!coequipiers.data) return null;
  return (
    <Card padding={20}>
      <Eyebrow>Mes coéquipiers de course</Eyebrow>
      {coequipiers.data.length === 0 ? (
        <p style={{ margin: "12px 0 0", fontSize: 14, color: "var(--tcn-text-muted)" }}>Aucun coéquipier de course sur cette sélection.</p>
      ) : (
        <ul style={{ margin: "12px 0 0", padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 12 }}>
          {coequipiers.data.map((c) => {
            const nom = `${c.prenom} ${c.nom}`;
            return (
              <li key={c.athlete_id}>
                <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "var(--tcn-ink)" }}>{nom}</p>
                <p style={{ margin: "2px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}>{`${motCompte(c.courses_communes, "épreuve")} en commun`}</p>
                <Link
                  href={`/athletes/${athleteId}?comparer=${c.athlete_id}`}
                  aria-label={`Me comparer à ${nom}`}
                  className="tcn-cible-tactile inline-flex items-center text-sm font-semibold text-accent-ink hover:underline"
                >
                  Me comparer
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

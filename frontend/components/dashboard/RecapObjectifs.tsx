"use client";

import { Card, Eyebrow, MetaPill } from "@/components/tcn";
import { useSeasonGoals } from "@/lib/queries/auth";
import { libelle, progression } from "./SeasonGoals";

/** Objectifs de la saison du récap (#1669), en lecture seule. Un échec de lecture masque la section sans bloquer le récap. */
export function RecapObjectifs({ season }: { season: number }) {
  const goals = useSeasonGoals(true, season);
  if (goals.isPending || goals.error || goals.data.length === 0) return null;

  return (
    <Card>
      <Eyebrow>Mes objectifs</Eyebrow>
      <ul style={{ listStyle: "none", padding: 0, margin: "12px 0 0", display: "grid", gap: 12 }}>
        {goals.data.map((goal) => (
          <li key={goal.id} style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10 }}>
            <div style={{ flex: "1 1 220px", minWidth: 0 }}>
              <div style={{ fontWeight: 700 }}>{libelle(goal)}</div>
              <div style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>{progression(goal)}</div>
            </div>
            {goal.reached ? (
              <MetaPill accent dot>Atteint</MetaPill>
            ) : (
              <MetaPill>{goal.outcome === "awaiting_results" ? "Sans résultat" : "Non atteint"}</MetaPill>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

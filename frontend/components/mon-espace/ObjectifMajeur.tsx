"use client";

import type { ReactNode } from "react";
import { hms, joursAvant, libelle, progression } from "@/components/dashboard/SeasonGoals";
import { Card, Eyebrow, MetaPill } from "@/components/tcn";
import { useSeasonGoals } from "@/lib/queries/auth";
import type { SeasonGoal } from "@/lib/types";
import { currentSeason } from "@/lib/utils/season";

/** Objectif majeur de la saison en cours, rien pendant le chargement, en erreur ou sans majeur. */
function useObjectifMajeur(): SeasonGoal | null {
  const goals = useSeasonGoals(true, currentSeason());
  return goals.data?.find((goal) => goal.major) ?? null;
}

function Verdict({ goal }: { goal: SeasonGoal }): ReactNode {
  if (goal.outcome === "reached") return <MetaPill accent dot>Atteint</MetaPill>;
  if (goal.outcome === "missed") return <MetaPill>Non atteint</MetaPill>;
  return null;
}

function CompteARebours({ goal }: { goal: SeasonGoal }) {
  const jours = joursAvant(goal);
  if (jours <= 0) return <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 40, color: "var(--tcn-ink)" }}>Aujourd&apos;hui</div>;
  return (
    <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 40, color: "var(--tcn-ink)" }}>
      <span aria-hidden="true">J‑{jours}</span>
      <span className="sr-only">dans {jours} {jours > 1 ? "jours" : "jour"}</span>
    </div>
  );
}

export function ObjectifMajeur() {
  const goal = useObjectifMajeur();
  if (goal === null) return null;
  const course = goal.kind === "race";
  const aVenir = course && goal.outcome === "upcoming";
  return (
    <Card>
      <Eyebrow>Objectif majeur</Eyebrow>
      <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: "8px 0 0" }}>
        {libelle(goal)}
      </h2>
      {aVenir && <CompteARebours goal={goal} />}
      {course && goal.target !== null && (
        <p style={{ margin: "4px 0 0", fontSize: 15 }}>Temps visé : {hms(goal.target)}</p>
      )}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, marginTop: 8 }}>
        {!aVenir && <span style={{ fontSize: 15 }}>{progression(goal)}</span>}
        <Verdict goal={goal} />
      </div>
    </Card>
  );
}

/** Rappel d'une ligne de l'objectif majeur, dans la colonne de droite. */
export function RappelObjectifMajeur() {
  const goal = useObjectifMajeur();
  if (goal === null) return null;
  return (
    <Card padding={20}>
      <Eyebrow>Objectif majeur</Eyebrow>
      <p style={{ margin: "12px 0 0", fontSize: 15, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <span>{libelle(goal)}</span>
        <Verdict goal={goal} />
      </p>
      <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}>{progression(goal)}</p>
    </Card>
  );
}

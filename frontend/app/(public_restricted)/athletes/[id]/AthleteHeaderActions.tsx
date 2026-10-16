"use client";

import { useEffect, useState } from "react";
import { useHydratedSession } from "@/lib/queries/auth";
import type { AthleteAdminPanel as Panel, CoureurACorriger } from "@/components/athletes/AthleteAdminPanel";
import { AthleteOppositionAction } from "@/components/athletes/AdminGates";
import { AthleteSelection } from "./AthleteSelection";

/**
 * Hiérarchie des deux commandes en haut à droite de la fiche athlète (#753,
 * audit UI/UX). Sans `athletes:write`, ordre et poids visuels restent ceux
 * d'avant : `AthleteSelection` primaire (ou secondaire une fois l'athlète
 * retenu, sa propre logique), `AthleteAdminPanel` toujours secondaire.
 *
 * Avec `athletes:write`, la tâche probable du visiteur sur cette page —
 * corriger la fiche, profil après profil — devient l'action primaire et
 * passe en tête ; la sélection, hors sujet pour lui, redescend en secondaire
 * sans perdre son bénéfice affiché (arbitrage de l'issue : le texte reste,
 * seuls le poids et l'ordre changent).
 *
 * Le panneau se charge à la demande (#1582), et la bascule attend qu'il soit
 * là : sinon la sélection redescendait seule en secondaire, puis se faisait
 * pousser par le bouton primaire arrivé un aller-retour plus tard. Sans
 * `athletes:write`, `AthleteAdminPanel` ne rend rien : il n'est pas monté.
 */
export function AthleteHeaderActions({ athlete }: { athlete: CoureurACorriger }) {
  const session = useHydratedSession();
  const peutCorriger = session.data?.permissions.includes("athletes:write") ?? false;
  const [AthleteAdminPanel, setPanel] = useState<typeof Panel | null>(null);

  useEffect(() => {
    if (!peutCorriger) return;
    import("@/components/athletes/AthleteAdminPanel").then((module) =>
      setPanel(() => module.AthleteAdminPanel),
    );
  }, [peutCorriger]);

  if (peutCorriger && AthleteAdminPanel) {
    return (
      <>
        <AthleteAdminPanel athlete={athlete} primary />
        <AthleteSelection athlete={athlete} primary={false} />
        <AthleteOppositionAction athlete={athlete} />
      </>
    );
  }

  return (
    <>
      <AthleteSelection athlete={athlete} />
      <AthleteOppositionAction athlete={athlete} />
    </>
  );
}

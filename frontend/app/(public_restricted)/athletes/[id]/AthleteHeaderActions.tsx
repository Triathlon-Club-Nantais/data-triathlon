"use client";

import { useSession } from "@/lib/queries/auth";
import { AthleteAdminPanel, type CoureurACorriger } from "@/components/athletes/AthleteAdminPanel";
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
 */
export function AthleteHeaderActions({ athlete }: { athlete: CoureurACorriger }) {
  const session = useSession();
  const peutCorriger = session.data?.permissions.includes("athletes:write") ?? false;

  if (peutCorriger) {
    return (
      <>
        <AthleteAdminPanel athlete={athlete} primary />
        <AthleteSelection athlete={athlete} primary={false} />
      </>
    );
  }

  return (
    <>
      <AthleteSelection athlete={athlete} />
      <AthleteAdminPanel athlete={athlete} />
    </>
  );
}

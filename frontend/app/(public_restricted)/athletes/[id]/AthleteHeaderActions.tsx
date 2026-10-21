"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useHydratedSession } from "@/lib/queries/auth";
import type { AthleteAdminPanel as Panel, CoureurACorriger } from "@/components/athletes/AthleteAdminPanel";
import { AthleteOppositionAction } from "@/components/athletes/AdminGates";
import { AthleteClaimAction, LinkedAthleteMark } from "@/components/athletes/AthleteClaimAction";
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

  const panneauEnTete = peutCorriger && AthleteAdminPanel;
  // #1325 : un compte rattaché ne choisit plus d'athlète, sa fiche tient lieu de
  // sélection ; un connecté sans rattachement peut demander celle-ci.
  const rattachee = session.data?.athlete;
  const selection = rattachee ? (
    <LinkedAthleteMark athlete={athlete} linked={rattachee} />
  ) : (
    <>
      <AthleteSelection athlete={athlete} primary={!panneauEnTete} />
      {session.data?.is_member && <AthleteClaimAction athlete={athlete} session={session.data} />}
      {session.data && !session.data.is_member && (
        <Link href="/mon-compte#demande-adhesion" className="tcn-cible-tactile inline-flex items-center text-sm underline underline-offset-2">
          {session.data.member_request?.status === "pending"
            ? "Voir ma demande d'adhésion (en attente)"
            : "Rejoindre le club pour rattacher votre fiche"}
        </Link>
      )}
    </>
  );

  return (
    <>
      {panneauEnTete && <AthleteAdminPanel athlete={athlete} primary />}
      {selection}
      <AthleteOppositionAction athlete={athlete} />
    </>
  );
}

"use client";

import { MetaPill } from "@/components/tcn";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const EXPLICATION_ID = "fiche-tenue-explication";
const EXPLICATION = "L'athlète a rattaché cette fiche à son compte de membre, après vérification par le club.";

/**
 * Pastille d'une fiche rattachée à un compte (#1693). L'infobulle ne vit qu'à
 * l'ouverture : l'explication reste donc aussi dans le DOM, en description du
 * déclencheur, pour les lecteurs d'écran.
 */
export function ClaimedAthleteBadge() {
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span tabIndex={0} aria-describedby={EXPLICATION_ID} className="rounded-full focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]" />}
      >
        <MetaPill accent dot>
          Fiche tenue par l&apos;athlète
        </MetaPill>
        <span id={EXPLICATION_ID} className="sr-only">
          {EXPLICATION}
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-72 whitespace-normal">
        {EXPLICATION}
      </TooltipContent>
    </Tooltip>
  );
}

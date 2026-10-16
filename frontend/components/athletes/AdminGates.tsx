"use client";
import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import { useHydratedSession } from "@/lib/queries/auth";

// Les sept gestes d'administration de la fiche athlète, chargés seulement une
// fois un pouvoir établi (#1582, motif de `CourseAdminActions`) : un visiteur
// sans pouvoir ne télécharge ni eux ni `lib/queries/admin.ts`. La garde n'est
// qu'un premier tri, chaque composant gardant la sienne, exacte.
function gate<P extends object>(powers: string[], Lazy: ComponentType<P>) {
  return function Gate(props: P) {
    const permissions = useHydratedSession().data?.permissions ?? [];
    if (!powers.some((power) => permissions.includes(power))) return null;
    return <Lazy {...props} />;
  };
}

export const AthleteAdminPanel = gate(
  ["athletes:write"],
  dynamic(() =>
    import("./AthleteAdminPanel").then((module) => module.AthleteAdminPanel),
  ),
);

export const AthleteOppositionAction = gate(
  ["oppositions:manage"],
  dynamic(() =>
    import("./AthleteOppositionAction").then((module) => module.AthleteOppositionAction),
  ),
);

export const ParticipationAdminActions = gate(
  ["participations:delete", "participations:reassign"],
  dynamic(() =>
    import("./ParticipationAdminActions").then((module) => module.ParticipationAdminActions),
  ),
);

export const AthleteDetachAction = gate(
  ["participations:reassign"],
  dynamic(() =>
    import("./AthleteDetachAction").then((module) => module.AthleteDetachAction),
  ),
);

export const SeasonValidationPanel = gate(
  ["athletes:season_validate"],
  dynamic(() =>
    import("./SeasonValidationPanel").then((module) => module.SeasonValidationPanel),
  ),
);

export const VolunteerActionsList = gate(
  ["athletes:volunteer_validate"],
  dynamic(() =>
    import("./VolunteerActionsList").then((module) => module.VolunteerActionsList),
  ),
);

export const AthleteVariantsPanel = gate(
  ["athletes:write"],
  dynamic(() =>
    import("./AthleteVariantsPanel").then((module) => module.AthleteVariantsPanel),
  ),
);

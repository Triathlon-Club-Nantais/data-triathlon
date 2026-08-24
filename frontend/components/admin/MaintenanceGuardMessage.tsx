"use client";
import { useSession } from "@/lib/queries/auth";

/**
 * `WipeCoursesCard` et `WipeParticipationsCard` testent chacune leur propre
 * pouvoir et se rendent `null` sans lui (#499) — la bonne garde, la navigation
 * n'en étant pas une. Mais une session qui porte un pouvoir d'admin, sans
 * aucun des deux `*:wipe_all`, et qui arrive par URL ou par signet, voyait
 * alors un écran réduit à son titre : muet, ce qui ne se distingue pas d'un
 * écran cassé (`AGENTS.md`).
 *
 * Petit composant **client** dédié, plutôt que rendre `page.tsx` client :
 * seul le test de pouvoir en a besoin, l'en-tête et le titre restent servis
 * par le composant serveur. Même formulation que `RolePermissionsEditor` et
 * `UserRolesTable`.
 */
export function MaintenanceGuardMessage() {
  const session = useSession();
  const peutAgir =
    (session.data?.permissions.includes("courses:wipe_all") ||
      session.data?.permissions.includes("participations:wipe_all")) ??
    false;
  if (session.isPending || peutAgir) return null;

  return (
    <p className="text-sm text-[var(--tcn-text-faint)]">
      Cet écran est en consultation : ces gestes demandent le pouvoir « Purger
      toutes les épreuves » ou « Purger tous les résultats ».
    </p>
  );
}

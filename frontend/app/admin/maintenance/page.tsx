"use client";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { Skeleton } from "@/components/ui/skeleton";
import { MaintenanceGuardMessage } from "@/components/admin/MaintenanceGuardMessage";
import { WipeCoursesCard } from "@/components/admin/WipeCoursesCard";
import { WipeParticipationsCard } from "@/components/admin/WipeParticipationsCard";
import { useSession } from "@/lib/queries/auth";

/**
 * Les gestes sans retour, et rien d'autre (#499, `ADM-7`).
 *
 * Ces deux purges vivaient en pied de `/admin/courses`, sous le tableau où l'on
 * vient corriger la date d'une épreuve : trois `Card` dans le même `space-y-6`,
 * donc un administrateur qui feuillette le catalogue jusqu'à la dernière page
 * et fait défiler se retrouvait à un clic de la destruction de toute la base.
 * Les replier sur place aurait caché le voisinage sans le supprimer.
 *
 * Aucune garde ici : le `layout.tsx` de `/admin` couvre ses sous-routes, chaque
 * carte teste son propre pouvoir, et la protection réelle est côté serveur.
 * `MaintenanceGuardMessage` couvre le seul trou que ça laisse : une session
 * qui porte un pouvoir d'admin sans aucun des deux `*:wipe_all` ne doit pas
 * voir un écran muet.
 *
 * Pendant que la session se charge, les trois enfants rendent `null` (chacun
 * teste son propre pouvoir) : sans ce composant `"use client"`, un réveil à
 * froid du backend Render laissait l'écran réduit à son titre (#499, revue de
 * fin de branche).
 *
 * Le `h2` de la section reste `sr-only` : `PageHeader` (`nav.config.ts`) dit
 * déjà « Les gestes sans retour … Rien ici ne se répare », et c'est le seul
 * `h2` d'un écran dont la section couvre tout. Il reste posé pour
 * `aria-labelledby`, sans redondance visuelle.
 */
export default function AdminMaintenancePage() {
  const session = useSession();

  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/maintenance")} />
        <section aria-labelledby="zone-de-dangers" className="space-y-6">
          <h2 id="zone-de-dangers" className="sr-only">
            Zone de danger
          </h2>
          {session.isPending ? (
            <>
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-40 w-full" />
            </>
          ) : (
            <>
              <MaintenanceGuardMessage />
              <WipeParticipationsCard />
              <WipeCoursesCard />
            </>
          )}
        </section>
      </div>
    </PageShell>
  );
}

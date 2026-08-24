import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { MaintenanceGuardMessage } from "@/components/admin/MaintenanceGuardMessage";
import { WipeCoursesCard } from "@/components/admin/WipeCoursesCard";
import { WipeParticipationsCard } from "@/components/admin/WipeParticipationsCard";

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
 */
export default function AdminMaintenancePage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/maintenance")} />
        <section aria-labelledby="zone-de-dangers" className="space-y-6">
          <h2 id="zone-de-dangers" className="font-heading text-lg text-destructive">
            Zone de dangers — gestes sans retour
          </h2>
          <MaintenanceGuardMessage />
          <WipeParticipationsCard />
          <WipeCoursesCard />
        </section>
      </div>
    </PageShell>
  );
}

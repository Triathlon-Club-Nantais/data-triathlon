import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * Racine de l'administration — le futur tableau de bord global.
 *
 * Vide et sans entrée de navigation tant qu'il n'a rien à montrer : les écrans
 * d'administration vivent chacun sous `/admin/<écran>`, et c'est la nav qui y
 * mène. Cette page tient l'URL, elle ne redirige pas — un `/admin` qui saute
 * ailleurs ferait croire que l'écran d'arrivée *est* la racine.
 */
export default function AdminPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader eyebrow="Maintenance" title="Administration" />
        <EmptyState
          title="Tableau de bord à venir"
          description="Choisissez un écran d'administration dans la navigation."
        />
      </div>
    </PageShell>
  );
}

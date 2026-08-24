import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { CoursesAdminTable } from "@/components/admin/CoursesAdminTable";

/**
 * Administration des épreuves (#117).
 *
 * Aucune garde ici : le `layout.tsx` de `/admin` couvre déjà ses sous-routes, et
 * il a été écrit pour ça. La protection réelle est de toute façon côté serveur,
 * route par route — cet écran ne fait que cacher ce qu'il ne peut pas faire.
 *
 * **C'est la page qui lit l'URL**, comme `/resultats`, et non le tableau via
 * `useSearchParams` : ce hook force une frontière `Suspense`, faute de quoi le
 * prérendu de cette route échoue au build. Le tableau, lui, écrit dans l'URL —
 * un `router.push` re-rend cette page, qui lui repasse le nouvel état.
 *
 * Les deux purges globales ont quitté ce pied de page pour `/admin/maintenance`
 * (#499) : on ne détruit pas la base depuis l'écran où l'on corrige une date.
 */
export default async function AdminCoursesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;

  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/courses")} />
        <CoursesAdminTable
          page={Number(sp.page)}
          filtres={{
            name: sp.name,
            event_type: sp.event_type,
            date_from: sp.date_from,
            date_to: sp.date_to,
          }}
        />
      </div>
    </PageShell>
  );
}

import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { QualityQueueTable } from "@/components/admin/QualityQueueTable";

/**
 * Revalidation qualité (#119).
 *
 * Aucune garde ici : le `layout.tsx` de `/admin` couvre déjà ses sous-routes, et
 * chaque geste porte la sienne côté serveur. **C'est la page qui lit l'URL**,
 * comme `/admin/courses` : `useSearchParams` dans le tableau forcerait une
 * frontière `Suspense`, faute de quoi le prérendu de la route échoue au build.
 */
export default async function AdminQualityPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;

  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader eyebrow="Administration" {...ecran("/admin/quality")} />
        <QualityQueueTable
          page={Number(sp.page)}
          filtres={{ name: sp.name, date_from: sp.date_from, date_to: sp.date_to }}
        />
      </div>
    </PageShell>
  );
}

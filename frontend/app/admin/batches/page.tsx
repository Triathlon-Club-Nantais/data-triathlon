import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { BatchLauncher } from "@/components/admin/BatchLauncher";
import { BatchRunList } from "@/components/admin/BatchRunList";
import { SheetUpload } from "@/components/admin/SheetUpload";

/**
 * Lancer et suivre les batches (#47).
 *
 * Sous `/admin`, donc couvert par `app/admin/layout.tsx`. Cette garde ne
 * protège aucune donnée : le lancement exige `batch:run` côté API, la
 * consultation `batch:read`, et les deux sont vérifiés route par route.
 *
 * Le batch ne tourne pas dans le service web mais sur un runner : cet écran ne
 * fait que demander, puis relire.
 */
export default function AdminBatchesPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/batches")} />
        <section className="space-y-4">
          <h2 className="text-lg font-bold">Reprise de la base</h2>
          <BatchLauncher />
        </section>
        <section className="space-y-4">
          <h2 className="text-lg font-bold">Import d&apos;un fichier</h2>
          <SheetUpload />
        </section>
        <section className="space-y-4">
          <h2 className="text-lg font-bold">Lancements récents</h2>
          <BatchRunList />
        </section>
      </div>
    </PageShell>
  );
}

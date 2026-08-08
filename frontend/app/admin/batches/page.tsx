import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { BatchLauncher } from "@/components/admin/BatchLauncher";
import { BatchRunList } from "@/components/admin/BatchRunList";

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
        <PageHeader
          eyebrow="Exploitation"
          title="Batches"
          description="Relancer le scraping des épreuves déjà en base, et relire le bilan des lancements précédents."
        />
        <BatchLauncher />
        <BatchRunList />
      </div>
    </PageShell>
  );
}

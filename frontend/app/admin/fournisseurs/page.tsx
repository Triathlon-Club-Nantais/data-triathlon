import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { PendingProvidersTable } from "@/components/admin/PendingProvidersTable";

export default function PendingProvidersPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader eyebrow="Maintenance" {...ecran("/admin/fournisseurs")} />
        <PendingProvidersTable />
      </div>
    </PageShell>
  );
}

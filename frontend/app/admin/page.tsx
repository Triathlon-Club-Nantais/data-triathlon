import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { PendingProvidersTable } from "@/components/admin/PendingProvidersTable";

export default function AdminPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Maintenance"
          title="Administration"
          description="Fournisseurs de chronométrage non supportés, signalés automatiquement lors d'un import en échec."
        />
        <PendingProvidersTable />
      </div>
    </PageShell>
  );
}

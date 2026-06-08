import { PageHeader } from "@/components/layout/PageHeader";
import { PendingProvidersTable } from "@/components/admin/PendingProvidersTable";

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Administration"
        description="Fournisseurs de chronométrage non supportés, signalés automatiquement lors d'un import en échec."
      />
      <PendingProvidersTable />
    </div>
  );
}

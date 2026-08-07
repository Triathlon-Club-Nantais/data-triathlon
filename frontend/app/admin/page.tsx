import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { PendingProvidersTable } from "@/components/admin/PendingProvidersTable";

/**
 * Un écran, un sujet. Les accès au back-office ont leur propre destination
 * (`/admin/acces`), sous la section « Gestion des utilisateurs » de la nav :
 * les empiler ici mêlait l'administration des personnes à celle des données.
 */
export default function AdminPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader
          eyebrow="Maintenance"
          title="Chronométreurs signalés"
          description="Fournisseurs non reconnus, signalés automatiquement lors d'un import en échec."
        />
        <PendingProvidersTable />
      </div>
    </PageShell>
  );
}

import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AdminVolunteerActionsTable } from "@/components/benevolat/AdminVolunteerActionsTable";

/**
 * Écran de validation des déclarations de crédit d'athlète (#779, jamais
 * construit avant #817) — remplace l'ancien contenu d'auto-déclaration
 * retiré par #816.
 */
export default function AdminBenevolatPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/benevolat")} />
        <AdminVolunteerActionsTable />
      </div>
    </PageShell>
  );
}

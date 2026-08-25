import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AdminActionLogTable } from "@/components/admin/AdminActionLogTable";

export default function AdminJournalPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/journal")} />
        <AdminActionLogTable />
      </div>
    </PageShell>
  );
}

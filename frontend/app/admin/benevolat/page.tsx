import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AdminVolunteerDeclarationCreateForm } from "@/components/benevolat/AdminVolunteerDeclarationCreateForm";
import { AdminVolunteerDeclarationTable } from "@/components/benevolat/AdminVolunteerDeclarationTable";

export default function AdminBenevolatPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/benevolat")} />
        <AdminVolunteerDeclarationCreateForm />
        <AdminVolunteerDeclarationTable />
      </div>
    </PageShell>
  );
}

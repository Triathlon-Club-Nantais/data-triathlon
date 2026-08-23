import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { CourseDuplicatesTable } from "@/components/admin/CourseDuplicatesTable";

export default function CourseDuplicatesPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader eyebrow="Maintenance" {...ecran("/admin/doublons")} />
        <CourseDuplicatesTable />
      </div>
    </PageShell>
  );
}

import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { FeedbackTable } from "@/components/admin/FeedbackTable";

export default function AdminFeedbackPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/retours-utilisateurs")} />
        <FeedbackTable />
      </div>
    </PageShell>
  );
}

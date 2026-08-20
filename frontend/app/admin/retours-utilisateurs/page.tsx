import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { FeedbackTable } from "@/components/admin/FeedbackTable";

export default function AdminFeedbackPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Maintenance"
          title="Retours utilisateurs"
          description="Signalements de bug et retours soumis depuis le bouton du site public."
        />
        <FeedbackTable />
      </div>
    </PageShell>
  );
}

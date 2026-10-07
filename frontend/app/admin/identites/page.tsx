import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { IdentityArbitrations } from "@/components/admin/ArbitrationUndoList";
import { AthleteIdentityReviewTable } from "@/components/admin/AthleteIdentityReviewTable";

export const metadata: Metadata = { title: ecran("/admin/identites").title };

export default function AthleteIdentitiesPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/identites")} />
        <AthleteIdentityReviewTable />
        <IdentityArbitrations />
      </div>
    </PageShell>
  );
}

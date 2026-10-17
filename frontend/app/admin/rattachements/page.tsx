"use client";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AthleteClaimsTable } from "@/components/admin/AthleteClaimsTable";

/** File des demandes de rattachement à une fiche athlète (#1325). */
export default function AdminRattachementsPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/rattachements")} />
        <AthleteClaimsTable />
      </div>
    </PageShell>
  );
}

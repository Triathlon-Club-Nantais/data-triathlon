import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AdminVolunteerActionsTable } from "@/components/benevolat/AdminVolunteerActionsTable";
import { PreviewRefusal, hasPagesPreview } from "@/components/layout/PreviewRefusal";
import { apiServer } from "@/lib/api/server";

export const metadata: Metadata = { title: ecran("/admin/benevolat").title };

/**
 * Écran de validation des déclarations de crédit d'athlète (#779, jamais
 * construit avant #817) — remplace l'ancien contenu d'auto-déclaration
 * retiré par #816. Derrière `pages:preview` (#879), avec les écrans publics
 * du bénévolat.
 */
export default async function AdminBenevolatPage() {
  if (!hasPagesPreview(await apiServer.getSession())) {
    return <PreviewRefusal header={<PageHeader {...ecran("/admin/benevolat")} />} />;
  }
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/benevolat")} />
        <AdminVolunteerActionsTable />
      </div>
    </PageShell>
  );
}

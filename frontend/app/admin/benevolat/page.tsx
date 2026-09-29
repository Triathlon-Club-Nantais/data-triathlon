import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AdminVolunteerActionsTable } from "@/components/benevolat/AdminVolunteerActionsTable";
import { previewGate } from "@/components/layout/PreviewRefusal";

export const metadata: Metadata = { title: ecran("/admin/benevolat").title };

/**
 * Écran de validation des déclarations de crédit d'athlète (#779, jamais
 * construit avant #817) — remplace l'ancien contenu d'auto-déclaration
 * retiré par #816. Derrière `pages:preview` (#879), avec les écrans publics
 * du bénévolat.
 */
export default async function AdminBenevolatPage() {
  const refus = await previewGate(<PageHeader {...ecran("/admin/benevolat")} />);
  if (refus) return refus;
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/benevolat")} />
        <AdminVolunteerActionsTable />
      </div>
    </PageShell>
  );
}

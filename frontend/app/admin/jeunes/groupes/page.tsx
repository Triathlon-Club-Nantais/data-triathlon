import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { GroupesList } from "@/components/admin/jeunes/GroupesList";

export const metadata: Metadata = { title: ecran("/admin/jeunes/groupes").title };

/** Les groupes d'entraînement (#1291). Garde effective côté API (`jeunes:read`/`jeunes:write`). */
export default function AdminJeunesGroupesPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/jeunes/groupes")} />
        <GroupesList />
      </div>
    </PageShell>
  );
}

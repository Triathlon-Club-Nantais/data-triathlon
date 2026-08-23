import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { GroupsTable } from "@/components/admin/GroupsTable";

/**
 * Troisième écran de la section « Gestion des utilisateurs » (#241).
 *
 * Sous `/admin`, donc couvert par `app/admin/layout.tsx` sans rien y ajouter.
 * Cette garde ne protège aucune donnée : les deux lectures exigent
 * `groups:read`, le cycle de vie d'un groupe `groups:write`, sa composition
 * `groups:assign`.
 */
export default function AdminGroupesPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/groupes")} />
        <GroupsTable />
      </div>
    </PageShell>
  );
}

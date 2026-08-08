import { PageHeader } from "@/components/layout/PageHeader";
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
        <PageHeader
          eyebrow="Gestion des utilisateurs"
          title="Groupes d'appartenance"
          description="À quoi chacun appartient — le Codir, les officiels, une section. Un groupe n'accorde aucun droit : ce que l'on peut faire vient des rôles."
        />
        <GroupsTable />
      </div>
    </PageShell>
  );
}

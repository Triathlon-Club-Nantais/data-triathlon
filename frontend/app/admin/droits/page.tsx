import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { RolePermissionsEditor } from "@/components/admin/RolePermissionsEditor";

/**
 * Deuxième écran de la section « Gestion des utilisateurs » (#240).
 *
 * Sous `/admin`, donc couvert par `app/admin/layout.tsx` sans rien y ajouter.
 * Cette garde ne protège aucune donnée : la lecture exige `roles:read` et
 * l'écriture `roles:write`, ressource par ressource, côté API.
 */
export default function AdminDroitsPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/droits")} />
        <RolePermissionsEditor />
      </div>
    </PageShell>
  );
}

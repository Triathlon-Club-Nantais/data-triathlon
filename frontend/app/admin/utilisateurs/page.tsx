import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { UserRolesTable } from "@/components/admin/UserRolesTable";

/**
 * Deuxième écran de la section « Gestion des utilisateurs » (#239).
 *
 * Sous `/admin`, donc couvert par `app/admin/layout.tsx` sans rien y ajouter.
 * Cette garde ne protège aucune donnée : la liste exige `users:read`,
 * l'inventaire des rôles `roles:read`, et les deux écritures `roles:assign`.
 */
export default function AdminUtilisateursPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/utilisateurs")} />
        <UserRolesTable />
      </div>
    </PageShell>
  );
}

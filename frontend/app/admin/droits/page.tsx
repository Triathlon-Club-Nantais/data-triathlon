import { PageHeader } from "@/components/layout/PageHeader";
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
        <PageHeader
          eyebrow="Gestion des utilisateurs"
          title="Droits des rôles"
          description="Un rôle porte des pouvoirs ; les personnes portent des rôles. Une recomposition s'applique dès la requête suivante de chaque porteur, sans reconnexion."
        />
        <RolePermissionsEditor />
      </div>
    </PageShell>
  );
}

import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { CalendrierEntrainements } from "@/components/admin/jeunes/CalendrierEntrainements";

/**
 * Le calendrier des entraînements jeunes (#868, epic #863).
 *
 * Sous `/admin`, donc couvert par `app/admin/layout.tsx` (SSO) sans rien y
 * ajouter — cette garde ne protège aucune donnée : les deux lectures exigent
 * `jeunes:read`, la création et la gestion des participants `jeunes:write`.
 */
export default function AdminJeunesCalendrierPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/jeunes/calendrier")} />
        <CalendrierEntrainements />
      </div>
    </PageShell>
  );
}

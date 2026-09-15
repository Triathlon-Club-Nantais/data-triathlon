import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { ProfileDetail } from "@/components/admin/ProfileDetail";

/**
 * Détail d'un profil (#867) — route dédiée plutôt qu'une modale, pour rester
 * mobile-first et partageable (research.md D3 de la feature : un panneau
 * latéral suppose une largeur que l'écran cible, le téléphone, n'a pas).
 */
export default async function AdminJeunePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader title="Profil" backHref="/admin/jeunes" backLabel="Retour aux jeunes" />
        <ProfileDetail profileId={Number(id)} />
      </div>
    </PageShell>
  );
}

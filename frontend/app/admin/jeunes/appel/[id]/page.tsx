import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { AppelPresence } from "@/components/admin/jeunes/AppelPresence";

/**
 * L'appel d'une séance donnée (#869, epic #863) — route dédiée plutôt qu'une
 * modale, même raisonnement que le détail d'un profil (#867) : mobile-first,
 * et partageable en cas de relais entre deux encadrants.
 */
export default async function AdminJeuneAppelPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader
          title="Appel"
          backHref="/admin/jeunes/calendrier"
          backLabel="Retour au calendrier"
        />
        <AppelPresence sessionId={Number(id)} />
      </div>
    </PageShell>
  );
}

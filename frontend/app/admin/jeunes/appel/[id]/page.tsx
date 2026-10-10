import type { Metadata } from "next";
import { PageShell } from "@/components/layout/PageShell";
import { idDeRoute } from "@/lib/utils/id-de-route";
import { AppelPresence } from "@/components/admin/jeunes/AppelPresence";

export const metadata: Metadata = { title: "Appel" };

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
  const sessionId = idDeRoute((await params).id);

  return (
    <PageShell>
      <AppelPresence sessionId={sessionId} />
    </PageShell>
  );
}

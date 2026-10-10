import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { ProfilesList } from "@/components/admin/ProfilesList";

export const metadata: Metadata = { title: ecran("/encadrement/jeunes").title };

/**
 * Écran « Jeunes » (#867, epic #863) — référencement des profils, mobile-first.
 *
 * Sous `/admin`, couvert par `app/admin/layout.tsx` sans rien y ajouter : la
 * garde effective est `jeunes:read`/`jeunes:write`, posée côté API sur chaque
 * route de `/admin/profiles` — cette page n'en est qu'un affichage.
 */
export default function AdminJeunesPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/encadrement/jeunes")} />
        <ProfilesList />
      </div>
    </PageShell>
  );
}

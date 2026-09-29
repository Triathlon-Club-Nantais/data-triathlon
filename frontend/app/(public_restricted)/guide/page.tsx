import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { GuideSommaire } from "@/components/guide/GuideSommaire";
import { GuideSection } from "@/components/guide/GuideSection";
import { GUIDE_MEMBRE } from "@/components/guide/guide-content.membre";
import { ROLE, destinationVisible } from "@/components/layout/nav.config";
import { apiServer } from "@/lib/api/server";

export const metadata: Metadata = { title: "Guide utilisateur" };

export default async function GuidePage() {
  // Même règle que le rail : une section ne décrit pas un écran tu au visiteur.
  const session = await apiServer.getSession();
  const rank = session ? ROLE.CONNECTED : ROLE.ANON;
  const pouvoirs = new Set(session?.permissions ?? []);
  const sections = GUIDE_MEMBRE.filter(
    (section) => !section.destination || destinationVisible(section.destination, pouvoirs, rank),
  );
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Guide"
          title="Guide utilisateur"
          description="Le mode d'emploi de chaque fonctionnalité, en quelques étapes."
        />
        <GuideSommaire sections={sections} />
        <div className="space-y-6">
          {sections.map((section) => (
            <GuideSection key={section.id} section={section} />
          ))}
        </div>
      </div>
    </PageShell>
  );
}

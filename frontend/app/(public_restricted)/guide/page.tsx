import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { GuideSommaire } from "@/components/guide/GuideSommaire";
import { GuideSection } from "@/components/guide/GuideSection";
import { GUIDE_MEMBRE } from "@/components/guide/guide-content.membre";

export default function GuidePage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Guide"
          title="Guide utilisateur"
          description="Le mode d'emploi de chaque fonctionnalité, en quelques étapes."
        />
        <GuideSommaire sections={GUIDE_MEMBRE} />
        <div className="space-y-6">
          {GUIDE_MEMBRE.map((section) => (
            <GuideSection key={section.id} section={section} />
          ))}
        </div>
      </div>
    </PageShell>
  );
}

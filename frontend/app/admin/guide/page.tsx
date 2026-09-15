import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { GuideSommaire } from "@/components/guide/GuideSommaire";
import { GuideSection } from "@/components/guide/GuideSection";
import { GUIDE_ADMIN } from "@/components/guide/guide-content.admin";

// Cette page n'est volontairement pas déclarée dans `nav.config.ts` (voir le
// commentaire sur `a-flags` dans ce fichier) : son `PageHeader` est donc
// rédigé ici, pas via `ecran()`.
export default function GuideAdminPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Administration"
          title="Guide"
          description="Le mode d'emploi de chaque écran du back-office, avec ses cas d'usage."
        />
        <GuideSommaire sections={GUIDE_ADMIN} />
        <div className="space-y-6">
          {GUIDE_ADMIN.map((section) => (
            <GuideSection key={section.id} section={section} />
          ))}
        </div>
      </div>
    </PageShell>
  );
}

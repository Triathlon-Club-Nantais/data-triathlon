import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { CourseDuplicatesTable } from "@/components/admin/CourseDuplicatesTable";

export default function CourseDuplicatesPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Maintenance"
          title="Doublons suspects"
          description="Paires d'épreuves qui désignent probablement le même événement — même URL, même identifiant de plateforme, ou noms proches à la même date."
        />
        <CourseDuplicatesTable />
      </div>
    </PageShell>
  );
}

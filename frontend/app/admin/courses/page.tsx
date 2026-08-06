import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { CoursesAdminTable } from "@/components/admin/CoursesAdminTable";

/**
 * Administration des épreuves (#117).
 *
 * Aucune garde ici : le `layout.tsx` de `/admin` couvre déjà ses sous-routes, et
 * il a été écrit pour ça. La protection réelle est de toute façon côté serveur,
 * route par route — cet écran ne fait que cacher ce qu'il ne peut pas faire.
 */
export default function AdminCoursesPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Administration"
          title="Épreuves"
          description="Corriger ou retirer une épreuve du catalogue. Ces actions sont irréversibles et tracées."
        />
        <CoursesAdminTable />
      </div>
    </PageShell>
  );
}

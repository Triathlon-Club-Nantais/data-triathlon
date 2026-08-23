import { AdminIndex } from "@/components/admin/AdminIndex";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";

/**
 * Racine de l'administration — le **sommaire** du back-office (ADM-6).
 *
 * Cette page tient l'URL, elle ne redirige pas : un `/admin` qui saute ailleurs
 * ferait croire que l'écran d'arrivée *est* la racine. Elle n'a pas d'entrée de
 * navigation pour autant — un `href` préfixe de tous les autres allumerait le
 * rail sur chaque écran d'administration (cf. `nav.config.ts`).
 */
export default function AdminPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Maintenance"
          title="Administration"
          description="Les écrans du back-office qui vous sont ouverts, et ce que chacun permet de faire."
        />
        <AdminIndex />
      </div>
    </PageShell>
  );
}

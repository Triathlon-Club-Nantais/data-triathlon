import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { PendingProvidersTable } from "@/components/admin/PendingProvidersTable";
import { Card } from "@/components/ui/card";

/**
 * Un écran, un sujet. Les accès au back-office ont leur propre destination
 * (`/admin/acces`), sous la section « Gestion des utilisateurs » de la nav :
 * les empiler ici mêlait l'administration des personnes à celle des données.
 */
export default function AdminPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader
          eyebrow="Maintenance"
          title="Chronométreurs signalés"
          description="Fournisseurs non reconnus, signalés automatiquement lors d'un import en échec."
        />
        {/* Sans ce lien, l'écran des épreuves n'existe que pour qui connaît son URL. */}
        <Card className="p-4">
          <Link href="/admin/courses" className="font-medium hover:underline">
            Administrer les épreuves →
          </Link>
          <p className="text-muted-foreground mt-1 text-sm">
            Corriger ou retirer une épreuve, rattacher un résultat au bon coureur.
          </p>
        </Card>
        <PendingProvidersTable />
      </div>
    </PageShell>
  );
}

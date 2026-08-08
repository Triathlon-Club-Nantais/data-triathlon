import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { AllowedEmailsTable } from "@/components/admin/AllowedEmailsTable";
import { RevokeSessionsCard } from "@/components/admin/RevokeSessionsCard";

/**
 * Premier écran de la section « Gestion des utilisateurs » (#170).
 *
 * Sous `/admin`, donc couvert par `app/admin/layout.tsx` sans rien y ajouter —
 * cette garde a été écrite pour couvrir les sous-routes à venir. Elle ne
 * protège aucune donnée : les trois ressources exigent `allowed_emails:manage`
 * côté API, et la révocation `sessions:revoke`.
 *
 * **Qui entre et qui reste entré tiennent au même endroit** (#169) : la
 * révocation par adresse vit dans le tableau, ligne par ligne, et la révocation
 * globale dans la carte ci-dessous. Les séparer aurait demandé un second écran
 * et une entrée de navigation pour un unique bouton.
 */
export default function AdminAccesPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader
          eyebrow="Gestion des utilisateurs"
          title="Accès au back-office"
          description="Seules ces adresses peuvent ouvrir une session. Une adresse retirée perd l'accès immédiatement."
        />
        <AllowedEmailsTable />
        <RevokeSessionsCard />
      </div>
    </PageShell>
  );
}

import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { RevokeSessionsCard } from "@/components/admin/RevokeSessionsCard";

/**
 * Révocation d'urgence des sessions (#169).
 *
 * Sous `/admin`, donc couvert par `app/admin/layout.tsx` sans rien y ajouter.
 * Cette garde ne protège aucune donnée : la ressource exige `sessions:revoke`
 * côté API.
 *
 * L'écran n'est pas le seul chemin, et ne doit pas l'être :
 * `python -m app.cli revoke-sessions --all` fait le même geste sans session,
 * pour le jour où c'est justement du back-office qu'on se méfie.
 *
 * Le geste **par compte** vit dans `/admin/utilisateurs`, au plus près de la
 * liste des personnes : cet écran-ci ne porte que le geste global, qui n'a pas
 * de ligne à désigner.
 */
export default function AdminSessionsPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader
          eyebrow="Administration"
          title="Sessions"
          description="Fermer d'un coup toutes les sessions ouvertes. Le geste d'incident, à distinguer du retrait d'un accès."
        />
        <RevokeSessionsCard />
      </div>
    </PageShell>
  );
}

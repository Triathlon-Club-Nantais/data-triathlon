import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { VolunteerActionForm } from "@/components/benevolat/VolunteerActionForm";

/**
 * Crédit du quota de saison d'un athlète (#778/#809) — seul chemin de
 * déclaration de bénévolat depuis le retrait de l'auto-déclaration (#751,
 * #816). Aucune garde de session individuelle : le mot de passe partagé du
 * site (`(public_restricted)`) suffit.
 */
export default function BenevolatPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Bénévolat"
          title="Créditer un athlète pour le quota de saison"
          description="Recherchez un athlète et décrivez l'activité de bénévolat qu'il a effectuée. La déclaration est instruite par un administrateur avant de compter pour son quota."
        />
        <VolunteerActionForm />
      </div>
    </PageShell>
  );
}

import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { VolunteerActionForm } from "@/components/benevolat/VolunteerActionForm";
import { EN_TETE_BENEVOLAT } from "@/components/benevolat/en-tete";

export const metadata: Metadata = { title: "Bénévolat" };

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
        <PageHeader {...EN_TETE_BENEVOLAT} />
        <VolunteerActionForm />
      </div>
    </PageShell>
  );
}

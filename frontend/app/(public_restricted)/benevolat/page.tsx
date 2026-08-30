"use client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/tcn";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { VolunteerDeclarationForm } from "@/components/benevolat/VolunteerDeclarationForm";
import { VolunteerDeclarationList } from "@/components/benevolat/VolunteerDeclarationList";
import { useSession } from "@/lib/queries/auth";

/**
 * Déclaration de bénévolat, self-service (#751).
 *
 * La garde `(public_restricted)` (mot de passe partagé du site) n'implique
 * **pas** une session individuelle — un visiteur ayant passé le mot de passe
 * du site peut rester anonyme côté identité (patron `UserMenu.tsx`). Sans
 * session, cette page invite à se connecter plutôt que d'afficher le
 * formulaire, qui exige `current_user` côté backend (401 sinon).
 */
export default function BenevolatPage() {
  const { data: session, isPending } = useSession();
  const router = useRouter();

  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Bénévolat"
          title="Déclarer une activité de bénévolat"
          description="Gardez une trace des activités de bénévolat que vous avez réalisées pour le club. Chaque déclaration est instruite par un administrateur."
        />
        {isPending ? null : !session ? (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8 }}>
            <Button onClick={() => router.push("/login")}>Se connecter</Button>
            <p style={{ margin: 0, color: "var(--tcn-text-muted)", fontSize: 14 }}>
              Une session est nécessaire pour déclarer une activité de bénévolat.
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            <VolunteerDeclarationForm />
            <VolunteerDeclarationList />
          </div>
        )}
      </div>
    </PageShell>
  );
}

"use client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/tcn";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { VolunteerActionForm } from "@/components/benevolat/VolunteerActionForm";
import { VolunteerDeclarationForm } from "@/components/benevolat/VolunteerDeclarationForm";
import { VolunteerDeclarationList } from "@/components/benevolat/VolunteerDeclarationList";
import { useSession } from "@/lib/queries/auth";

/**
 * Déclaration de bénévolat, self-service (#751), et formulaire de crédit du
 * quota de saison d'un athlète (#778) — deux sections distinctes sur la même
 * page (research.md D7 de #778) : la première trace la vie associative d'un
 * membre (`VolunteerDeclaration`), la seconde crédite le quota de saison d'un
 * athlète quelconque (`VolunteerAction`, #709) — deux tables indépendantes.
 *
 * La garde `(public_restricted)` (mot de passe partagé du site) n'implique
 * **pas** une session individuelle — un visiteur ayant passé le mot de passe
 * du site peut rester anonyme côté identité (patron `UserMenu.tsx`). Depuis
 * #809, seule la section d'auto-déclaration (#751, nominative par nature)
 * exige une session SSO côté backend (`current_user`, 401 sinon) — la
 * section de crédit d'un athlète (#778) ne l'exige plus (`optional_user`),
 * elle se rend donc toujours, avec ou sans session.
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
        <div className="space-y-10">
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
          <div className="space-y-6">
            {/* `h2`, pas un second `PageHeader` (qui rend toujours un `h1`,
                WCAG 1.3.1) — deux sections sur une même page, une seule
                hiérarchie de titres. */}
            <div className="space-y-1.5">
              <div className="eyebrow">Quota de saison</div>
              <h2 className="font-heading text-[22px] leading-none tracking-tight text-foreground sm:text-[28px]">
                Créditer un athlète pour le quota de saison
              </h2>
              <p className="max-w-2xl text-sm text-[var(--tcn-text-faint)]">
                Recherchez un athlète et décrivez l&apos;activité de bénévolat qu&apos;il a
                effectuée. La déclaration est instruite par un administrateur avant de compter
                pour son quota.
              </p>
            </div>
            <VolunteerActionForm />
          </div>
        </div>
      </div>
    </PageShell>
  );
}

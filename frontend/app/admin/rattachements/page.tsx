"use client";
import type { ReactNode } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AthleteClaimsTable } from "@/components/admin/AthleteClaimsTable";
import { AthleteLinksTable } from "@/components/admin/AthleteLinksTable";
import { ClaimKind } from "@/components/admin/ClaimKind";
import { ResultClaimsTable } from "@/components/admin/ResultClaimsTable";

/**
 * File commune des rattachements (#1325, #1637) et comptes rattachés (#1633).
 * Les deux sortes de demandes ne se confondent jamais : section, pastille,
 * explication et verbe d'action propres à chacune.
 */
export default function AdminRattachementsPage() {
  return (
    <PageShell>
      <div className="space-y-12">
        <PageHeader {...ecran("/admin/rattachements")} />
        <Section
          id="fiches-demandees"
          titre="Fiches demandées"
          sorte={<ClaimKind kind="record" />}
          explication="Un compte demande à être rattaché à une fiche athlète entière. « Rattacher la fiche » lui donne son espace personnel et, si la fiche est licenciée au club cette saison, le statut adhérent."
        >
          <AthleteClaimsTable />
        </Section>
        <Section
          id="resultats-reclames"
          titre="Résultats réclamés"
          sorte={<ClaimKind kind="result" />}
          explication="Un compte déjà rattaché réclame un seul résultat rangé sur une autre fiche, souvent celle d'un homonyme. « Déplacer le résultat » le passe sur sa fiche, le fige contre les réimports et supprime la fiche d'origine si elle se vide."
        >
          <ResultClaimsTable titreId="resultats-reclames" />
        </Section>
        <Section
          id="comptes-rattaches"
          titre="Comptes rattachés"
          explication="Les comptes déjà rattachés, ceux dont la fiche n'est plus licenciée cette saison en tête. « Détacher » sert au départ d'un adhérent."
        >
          <AthleteLinksTable />
        </Section>
      </div>
    </PageShell>
  );
}

function Section({
  id,
  titre,
  sorte,
  explication,
  children,
}: {
  id: string;
  titre: string;
  sorte?: ReactNode;
  explication: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-4" aria-labelledby={id}>
      <div className="space-y-1">
        <h2 id={id} tabIndex={-1} className="flex flex-wrap items-center gap-3 font-[var(--tcn-font-display)] text-xl">
          {titre}
          {sorte}
        </h2>
        <p className="max-w-3xl text-sm text-muted-foreground">{explication}</p>
      </div>
      {children}
    </section>
  );
}

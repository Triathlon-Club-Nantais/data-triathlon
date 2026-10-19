"use client";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AthleteClaimsTable } from "@/components/admin/AthleteClaimsTable";
import { AthleteLinksTable } from "@/components/admin/AthleteLinksTable";

const titreSection = "font-[var(--tcn-font-display)] text-xl";

/** File des demandes de rattachement (#1325) et comptes rattachés (#1633). */
export default function AdminRattachementsPage() {
  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/rattachements")} />
        <section className="space-y-4" aria-labelledby="demandes-en-attente">
          <h2 id="demandes-en-attente" className={titreSection}>Demandes en attente</h2>
          <AthleteClaimsTable />
        </section>
        <section className="space-y-4" aria-labelledby="comptes-rattaches">
          <h2 id="comptes-rattaches" className={titreSection}>Comptes rattachés</h2>
          <AthleteLinksTable />
        </section>
      </div>
    </PageShell>
  );
}

import type { Metadata } from "next";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { SeasonRecap } from "@/components/dashboard/SeasonRecap";
import { currentSeason } from "@/lib/utils/season";

export const metadata: Metadata = { title: "Récap de saison" };

/** Récap d'une saison close de l'athlète rattaché (#1372) ; `?saison=` borné à la dernière close. */
export default async function SeasonRecapPage({ searchParams }: { searchParams: Promise<{ saison?: string }> }) {
  const { saison } = await searchParams;
  const lastClosed = currentSeason() - 1;
  const demandee = Number(saison);
  const season = Number.isInteger(demandee) && demandee >= 2000 && demandee <= lastClosed ? demandee : lastClosed;

  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader eyebrow="Mon espace" title="Récap de saison" description="Vos épreuves, podiums et meilleurs temps." />
        <SeasonRecap season={season} lastClosed={lastClosed} />
      </div>
    </PageShell>
  );
}

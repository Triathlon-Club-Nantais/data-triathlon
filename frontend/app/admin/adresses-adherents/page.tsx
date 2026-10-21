"use client";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { MemberRequestsTable } from "@/components/admin/MemberRequestsTable";
import { MemberEmailsPanel } from "@/components/admin/MemberEmailsPanel";
import { EmptyState } from "@/components/ui/empty-state";
import { messageDeRefus } from "@/lib/api/refus";
import { useMemberEmails } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { currentSeason } from "@/lib/utils/season";

/**
 * Adresses d'adhérents par saison (#1334).
 *
 * Un seul pouvoir pour lire et écrire (`member_emails:manage`) : un refus de
 * lecture rend l'écran entier passif, et se dit une seule fois.
 */
export default function AdminAdressesAdherentsPage() {
  const [season, setSeason] = useState(() => currentSeason());
  const { data, isLoading, error } = useMemberEmails(season);
  const session = useSession();
  const peutValider = session.data?.permissions.includes("member_requests:review") ?? false;

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/adresses-adherents")} />
        {peutValider && (
          <section className="space-y-4" aria-labelledby="demandes-adhesion">
            <h2 id="demandes-adhesion" className="font-[var(--tcn-font-display)] text-xl">
              Demandes d&apos;adhésion
            </h2>
            <MemberRequestsTable />
          </section>
        )}
        {error ? (
          <EmptyState
            {...messageDeRefus(error, {
              sujet: "adresses d'adhérents",
              action: "gérer les adresses d'adhérents",
            })}
          />
        ) : (
          <MemberEmailsPanel season={season} onSeasonChange={setSeason} data={data} isLoading={isLoading} />
        )}
      </div>
    </PageShell>
  );
}

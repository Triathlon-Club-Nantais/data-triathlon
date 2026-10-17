"use client";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { MemberEmailsPanel } from "@/components/admin/MemberEmailsPanel";
import { EmptyState } from "@/components/ui/empty-state";
import { messageDeRefus } from "@/lib/api/refus";
import { useMemberEmails } from "@/lib/queries/admin";
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

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/adresses-adherents")} />
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

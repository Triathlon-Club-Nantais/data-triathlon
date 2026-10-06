"use client";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { ClubMembersPanel } from "@/components/admin/ClubMembersPanel";
import { EmptyState } from "@/components/ui/empty-state";
import { messageDeRefus } from "@/lib/api/refus";
import { useClubMembers } from "@/lib/queries/admin";
import { currentSeason } from "@/lib/utils/season";

/**
 * Licenciés du club par saison (#1202).
 *
 * Un seul pouvoir pour lire et écrire (`club_members:manage`) : un refus de
 * lecture rend l'écran entier passif, et se dit une seule fois.
 */
export default function AdminMembresPage() {
  const [season, setSeason] = useState(() => currentSeason());
  const { data, isLoading, error } = useClubMembers(season);

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/membres")} />
        {error ? (
          <EmptyState
            {...messageDeRefus(error, {
              sujet: "licenciés du club",
              action: "gérer les licenciés du club",
            })}
          />
        ) : (
          <ClubMembersPanel season={season} onSeasonChange={setSeason} data={data} isLoading={isLoading} />
        )}
      </div>
    </PageShell>
  );
}

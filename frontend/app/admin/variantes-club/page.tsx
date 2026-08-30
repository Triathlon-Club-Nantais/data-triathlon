// frontend/app/admin/variantes-club/page.tsx
"use client";
import { ClubAliasCard } from "@/components/admin/ClubAliasCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { EmptyState } from "@/components/ui/empty-state";
import { messageDeRefus } from "@/lib/api/refus";
import { useClubAliases } from "@/lib/queries/admin";

/**
 * Fusion des variantes de libellé de club, généralisée à tout club (#635,
 * suite #215). `club_aliases:manage` couvre lecture et écriture, donc un
 * refus rend l'écran entier passif — même patron que la portée des
 * compteurs, dont ce mécanisme reste pourtant indépendant.
 */
export default function AdminVariantesClubPage() {
  const { data, isLoading, error } = useClubAliases();

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/variantes-club")} />
        {error ? (
          <EmptyState
            {...messageDeRefus(error, {
              sujet: "variantes de libellé de club",
              action: "gérer les variantes de club",
            })}
          />
        ) : (
          <ClubAliasCard entrees={data?.entries} isLoading={isLoading} />
        )}
      </div>
    </PageShell>
  );
}

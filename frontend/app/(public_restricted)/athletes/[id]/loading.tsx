import { PageShell } from "@/components/layout/PageShell";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <PageShell>
      {/* Ligne de retour + rangée de pastilles : l'en-tête réel (`PageHeader`
          + `MetaPill`) les rend désormais, ~71px de plus que l'ancien
          squelette. Sans eux le contenu sautait vers le bas à l'arrivée des
          données, sur tous les profils (#488, revue UI/UX). */}
      <Skeleton className="mb-3 h-5 w-40" />
      <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 12 }}>
        <Skeleton className="size-[72px] shrink-0 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-10 w-56" />
        </div>
      </div>
      <div className="mb-7 flex gap-2">
        <Skeleton className="h-6 w-24 rounded-full" />
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      {/* Trois tuiles, pas cinq : le squelette ne peut pas connaître le
          régime (complet/réduit/vide) avant que les données n'arrivent, et
          trois est le majorant du cas fréquent — 47% des membres tombent en
          régime réduit ou vide, à qui cinq tuiles promettaient plus qu'elles
          n'en rendraient (#488). */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-96 w-full rounded-lg" />
    </PageShell>
  );
}

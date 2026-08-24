import { PageShell } from "@/components/layout/PageShell";
import { Skeleton } from "@/components/ui/skeleton";

// Même raison que `../loading.tsx` (#487). La barre de retour, l'en-tête, la
// ligne de tags de saison, puis la liste.
export default function Loading() {
  return (
    <PageShell>
      <div className="space-y-8">
        <div className="space-y-3">
          <Skeleton className="h-4 w-28" />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-10 w-72" />
              <Skeleton className="h-4 w-80" />
            </div>
            <Skeleton className="h-9 w-72" />
          </div>
          <Skeleton className="h-6 w-48 sm:ml-auto" />
        </div>
        <Skeleton className="h-96 w-full rounded-lg" />
      </div>
    </PageShell>
  );
}

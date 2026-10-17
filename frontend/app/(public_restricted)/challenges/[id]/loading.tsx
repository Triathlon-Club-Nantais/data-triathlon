import { PageShell } from "@/components/layout/PageShell";
import { Skeleton } from "@/components/ui/skeleton";
import { AnnonceStatut, Card } from "@/components/tcn";

/** Calqué sur `page.tsx` : en-tête, carte de description, carte du tableau. */
export default function Loading() {
  return (
    <PageShell>
      <AnnonceStatut texte="Chargement du classement du challenge" />
      <div aria-busy="true">
        <div className="mb-6 space-y-1.5">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-7 w-3/4 max-w-xl sm:h-10" />
        </div>
        <div className="space-y-6">
          <Card>
            <Skeleton className="h-6 w-full" />
          </Card>
          <Card>
            <div className="space-y-1">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-6 w-full" />
              ))}
            </div>
          </Card>
        </div>
      </div>
    </PageShell>
  );
}

import { Skeleton } from "@/components/ui/skeleton";

/** Corps de page de Mon espace en chargement : rangée de chiffres, colonne centrale, colonne de droite. */
export function SqueletteMonEspace() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-6">
        <div className="grid grid-cols-[repeat(auto-fill,minmax(8rem,1fr))] gap-4">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} data-testid="squelette-chiffre" className="h-16 w-full rounded-lg" />
          ))}
        </div>
        <Skeleton data-testid="squelette-centre" className="h-72 w-full rounded-lg" />
      </div>
      <Skeleton data-testid="squelette-droite" className="hidden h-72 w-full rounded-lg lg:block" />
    </div>
  );
}

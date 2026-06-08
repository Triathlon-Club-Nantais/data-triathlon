"use client";
import { useLiveFeed } from "@/lib/queries/stats";
import { ResultCard } from "@/components/results/ResultCard";
import { Skeleton } from "@/components/ui/skeleton";

export function LiveFeed({ club }: { club?: string }) {
  const { data, isLoading } = useLiveFeed(club);

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (!data || data.length === 0) {
    return <p className="text-muted-foreground">Aucun résultat récent.</p>;
  }
  return (
    <div className="space-y-3">
      {data.map((p) => (
        <ResultCard key={p.id} result={p} />
      ))}
    </div>
  );
}

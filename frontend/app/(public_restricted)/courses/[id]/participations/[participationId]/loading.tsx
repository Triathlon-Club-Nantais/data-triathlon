import { PageShell } from "@/components/layout/PageShell";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <PageShell>
      <Skeleton className="mb-3 h-4 w-72" />
      <div className="space-y-2" style={{ marginBottom: 26 }}>
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-10 w-64" />
      </div>
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-40 w-full rounded-lg" />
        ))}
      </div>
    </PageShell>
  );
}

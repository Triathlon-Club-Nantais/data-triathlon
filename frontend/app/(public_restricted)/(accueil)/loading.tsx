import { PageShell } from "@/components/layout/PageShell";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <PageShell>
      <div className="mb-4 flex lg:justify-end">
        <Skeleton className="h-14 w-full rounded-lg lg:w-72" />
      </div>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Skeleton className="h-60 w-full rounded-lg" />
        <Skeleton className="h-60 w-full rounded-lg" />
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-24 w-full rounded-lg" />
        ))}
      </div>
      <Skeleton className="mt-6 h-[26rem] w-full rounded-lg" />
    </PageShell>
  );
}

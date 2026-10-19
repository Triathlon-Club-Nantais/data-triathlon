import { PageShell } from "@/components/layout/PageShell";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <PageShell>
      <div className="space-y-3" style={{ marginBottom: 26 }}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <Skeleton className="h-3 w-40" />
            <Skeleton className="h-9 w-64" />
          </div>
          <Skeleton className="h-9 w-72" />
        </div>
      </div>
      <Skeleton className="h-40 w-full rounded-lg" />
    </PageShell>
  );
}

import { PageShell } from "@/components/layout/PageShell";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <PageShell form>
      <div className="space-y-2" style={{ marginBottom: 20 }}>
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-11 w-64" />
      </div>
      <Skeleton className="mb-6 h-40 w-full rounded-lg" />
      <Skeleton className="h-64 w-full rounded-lg" />
    </PageShell>
  );
}

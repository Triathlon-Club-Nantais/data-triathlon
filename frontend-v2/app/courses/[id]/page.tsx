import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { SportBadge } from "@/components/results/SportBadge";
import { Leaderboard } from "@/components/results/Leaderboard";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils/date";
import { isTCN } from "@/lib/utils/club";

export default async function CoursePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer.getCourse(Number(id)).catch(() => null);
  if (!data) notFound();
  const { course, participations } = data;
  const tcnCount = participations.filter((p) => isTCN(p.club)).length;

  return (
    <div className="space-y-6">
      <PageHeader
        backHref="/resultats"
        title={course.name}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <SportBadge type={course.event_type} />
            {course.event_date && <span>{formatDate(course.event_date)}</span>}
            {course.is_relay && <Badge variant="destructive">Relais</Badge>}
          </span>
        }
      >
        <div className="flex flex-wrap gap-2 pt-1">
          <Badge variant="secondary">
            {participations.length} participant{participations.length > 1 ? "s" : ""}
          </Badge>
          {tcnCount > 0 && <Badge>{tcnCount} membre{tcnCount > 1 ? "s" : ""} TCN</Badge>}
        </div>
      </PageHeader>

      {participations.length === 0 ? (
        <EmptyState title="Aucun participant" />
      ) : (
        <Leaderboard participations={participations} />
      )}
    </div>
  );
}

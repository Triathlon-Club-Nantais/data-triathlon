import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { ResultCard } from "@/components/results/ResultCard";
import { SportBadge } from "@/components/results/SportBadge";
import { formatDate } from "@/lib/utils/date";

export default async function CoursePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer.getCourse(Number(id)).catch(() => null);
  if (!data) notFound();
  const { course, participations } = data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold">{course.name}</h1>
        <SportBadge type={course.event_type} />
        {course.event_date && (
          <span className="text-muted-foreground">{formatDate(course.event_date)}</span>
        )}
      </div>
      <p className="text-muted-foreground">
        {participations.length} participant{participations.length > 1 ? "s" : ""}
      </p>
      <div className="space-y-3">
        {participations.map((p) => (
          <ResultCard key={p.id} result={p} />
        ))}
      </div>
    </div>
  );
}

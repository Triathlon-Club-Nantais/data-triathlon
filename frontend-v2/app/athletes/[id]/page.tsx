import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { PageHeader } from "@/components/layout/PageHeader";
import { ResultCard } from "@/components/results/ResultCard";
import { InitialsAvatar } from "@/components/ui/initials-avatar";
import { Stat } from "@/components/ui/stat";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { isPodium, recentParticipations } from "@/lib/utils/club-aggregate";

export default async function AthletePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const data = await apiServer.getAthlete(Number(id)).catch(() => null);
  if (!data) notFound();
  const { athlete, participations } = data;
  const fullName = [athlete.prenom, athlete.nom].filter(Boolean).join(" ");

  const podiums = participations.filter(isPodium).length;
  const disciplines = new Set(
    participations.map((p) => p.course?.event_type).filter(Boolean),
  ).size;
  const ordered = recentParticipations(participations, participations.length);

  return (
    <div className="space-y-6">
      <PageHeader
        backHref="/resultats"
        title={
          <span className="flex items-center gap-3">
            <InitialsAvatar name={fullName} size={44} />
            {fullName}
          </span>
        }
        description={athlete.club ?? "Sans club"}
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <KpiCard label="Courses" value={participations.length} accent />
        <KpiCard label="Podiums" value={podiums} />
        <KpiCard label="Disciplines" value={disciplines} />
      </div>

      {ordered.length === 0 ? (
        <EmptyState title="Aucun résultat pour cet athlète" />
      ) : (
        <div className="space-y-3">
          {ordered.map((p) => (
            <ResultCard key={p.id} result={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function KpiCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <Card>
      <CardContent>
        <Stat value={value} label={label} accent={accent} />
      </CardContent>
    </Card>
  );
}

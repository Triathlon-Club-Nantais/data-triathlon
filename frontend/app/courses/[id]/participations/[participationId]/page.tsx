import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import {
  ComparisonTable,
  ImprovementMatrix,
  RankingEvolutionChart,
  ResultRow,
  UnavailableState,
} from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { formatDate } from "@/lib/utils/date";

/**
 * Détail d'une participation : la performance de l'athlète confrontée au
 * classement complet de sa course.
 *
 * L'URL porte la course **et** la participation alors que l'API n'a besoin que
 * de la seconde : c'est ce qui rend le lien lisible et partageable depuis les
 * deux points d'entrée (tableau des finishers, fiche athlète). Une
 * participation qui n'appartient pas à la course de l'URL est traitée comme
 * introuvable, sans quoi n'importe quel `courseId` afficherait la même page.
 */
export default async function ParticipationDetailPage({
  params,
}: {
  params: Promise<{ id: string; participationId: string }>;
}) {
  const { id, participationId } = await params;
  const participation = await apiServer
    .getParticipation(Number(participationId))
    .catch(() => null);

  if (!participation || participation.course?.id !== Number(id)) notFound();

  const athleteId = participation.athlete.id;
  const returns = <ReturnLinks courseId={id} athleteId={athleteId} />;

  if (!participation.stats) {
    return (
      <PageShell>
        {returns}
        <UnavailableState />
      </PageShell>
    );
  }

  const { stats, course } = participation;
  const eventDate = formatDate(course?.event_date);

  return (
    <PageShell>
      {returns}
      <PageHeader
        eyebrow="Détail du résultat"
        title={<Link href={`/courses/${id}`}>{course?.name ?? "Épreuve"}</Link>}
        description={eventDate || undefined}
      />

      <div style={{ marginTop: 26 }}>
        <ResultRow
          participation={participation}
          segments={stats.segments}
          steps={stats.ranking_evolution}
        />
        <ComparisonTable
          rows={stats.comparison}
          segments={stats.segments}
          eventType={course?.event_type ?? ""}
        />
        <RankingEvolutionChart
          steps={stats.ranking_evolution}
          eventType={course?.event_type ?? ""}
        />
        <ImprovementMatrix
          rows={stats.improvement}
          eventType={course?.event_type ?? ""}
        />
      </div>
    </PageShell>
  );
}

/**
 * Les deux retours de la page, rendus dans les deux états (statistiques
 * calculées ou non) : on arrive ici depuis le tableau des finishers **ou**
 * depuis la fiche athlète, et un seul retour renvoie la moitié des visiteurs
 * là d'où ils ne viennent pas.
 */
function ReturnLinks({ courseId, athleteId }: { courseId: string; athleteId: number }) {
  const links = [
    { href: `/courses/${courseId}`, label: "Retour à la course" },
    { href: `/athletes/${athleteId}`, label: "Retour aux résultats de l'athlète" },
  ];

  return (
    <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-2">
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="size-4" />
          {link.label}
        </Link>
      ))}
    </div>
  );
}

import Link from "next/link";
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

  if (!participation.stats) {
    return (
      <PageShell>
        <UnavailableState athleteId={athleteId} />
      </PageShell>
    );
  }

  const { stats, course } = participation;
  const eventDate = formatDate(course?.event_date);

  return (
    <PageShell>
      <PageHeader
        eyebrow="Détail du résultat"
        title={course?.name ?? "Épreuve"}
        description={eventDate || undefined}
        backHref={`/athletes/${athleteId}`}
        backLabel="Retour aux résultats de l'athlète"
        actions={
          <Link
            href="/ajouter"
            style={{
              padding: "8px 16px",
              borderRadius: "var(--tcn-radius-md)",
              border: "1px solid var(--tcn-border)",
              fontSize: 13,
              fontWeight: 700,
              color: "var(--tcn-ink)",
            }}
          >
            Ajouter un triathlon
          </Link>
        }
      />

      <div style={{ marginTop: 26 }}>
        <ResultRow participation={participation} segments={stats.segments} />
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

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { ApiError } from "@/lib/api/client";
import {
  Card,
  ComparisonTable,
  ImprovementMatrix,
  RankingEvolutionChart,
  ResultRow,
  UnavailableState,
} from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { formatDate } from "@/lib/utils/date";
import { ordinalFr } from "@/lib/utils/format";
import { Histogram } from "@/components/charts/Histogram";
import { CategoryBars } from "@/components/charts/CategoryBars";
import { parseTotalTimeSeconds } from "@/lib/utils/histogram-ticks";

/**
 * Synthèse d'épreuve absente traitée comme optionnelle plutôt que fatale
 * (US2/US3, #466) : l'histogramme et le repère de catégorie sont un
 * enrichissement de cet écran, pas sa raison d'être — une synthèse en panne
 * ne doit pas faire disparaître le détail de participation lui-même.
 */
function rendreNullSi404(erreur: unknown): null {
  if (erreur instanceof ApiError && erreur.status === 404) return null;
  throw erreur;
}

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
  // Deux appels indépendants, en parallèle : la synthèse d'épreuve (US2/US3,
  // #466) ne conditionne jamais le 404 de la participation elle-même.
  const [participation, summary] = await Promise.all([
    apiServer.getParticipation(Number(participationId)).catch(() => null),
    apiServer.getCourseSummary(Number(id)).catch(rendreNullSi404),
  ]);

  if (!participation || participation.course.id !== Number(id)) notFound();

  const athleteId = participation.athlete.id;
  const returns = <ReturnLinks courseId={id} athleteId={athleteId} />;

  const { stats, course } = participation;
  const eventDate = formatDate(course.event_date);
  const segments = stats?.segments ?? Object.keys(participation.splits ?? {});
  const markerSec = parseTotalTimeSeconds(participation.total_time);
  // Dénominateur du classement en catégorie (US3, #466) : `summary.categories`
  // ne porte que les 8 catégories les plus fournies (RES-7, hors périmètre) —
  // une catégorie absente de cette liste n'affiche aucun dénominateur plutôt
  // qu'un chiffre faux.
  const categoryCount = summary?.categories?.find((c) => c.name === participation.category);

  return (
    <PageShell>
      {returns}
      <PageHeader
        eyebrow="Détail du résultat"
        title={<Link href={`/courses/${id}`}>{course.name}</Link>}
        description={eventDate || undefined}
      />

      <div style={{ marginTop: 26 }}>
        <ResultRow
          participation={participation}
          segments={segments}
          steps={stats?.ranking_evolution ?? []}
        />
        {stats ? (
          <>
            <ComparisonTable
              rows={stats.comparison}
              segments={stats.segments}
              eventType={course.event_type}
            />
            <RankingEvolutionChart
              steps={stats.ranking_evolution}
              eventType={course.event_type}
            />
            <ImprovementMatrix
              rows={stats.improvement}
              eventType={course.event_type}
            />
          </>
        ) : (
          <UnavailableState />
        )}

        {summary?.histogram && (
          <Card padding={28} style={{ marginTop: 18 }}>
            <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0, marginBottom: 4 }}>Distribution des temps des arrivants</h2>
            <div style={{ fontSize: 13, color: "var(--tcn-text-muted)", marginBottom: 18 }}>Nombre d&apos;athlètes par tranche de 5 minutes — votre temps est repéré</div>
            <Histogram
              bars={summary.histogram.bars}
              max={Math.max(...summary.histogram.bars)}
              startSec={summary.histogram.start_sec}
              bucketSec={summary.histogram.bucket_sec}
              markerSec={markerSec}
            />
          </Card>
        )}

        {summary && summary.categories && summary.categories.length > 0 && (
          <Card padding={28} style={{ marginTop: 18 }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 4 }}>
              <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>Répartition par catégorie</h2>
              {participation.rank_category != null && categoryCount && (
                <div style={{ fontFamily: "var(--tcn-font-cond)", fontWeight: 700, fontSize: 20, color: "var(--tcn-ink)" }}>
                  {ordinalFr(participation.rank_category)} / {categoryCount.count}
                </div>
              )}
            </div>
            <div style={{ fontSize: 13, color: "var(--tcn-text-muted)", marginBottom: 18 }}>
              Nombre d&apos;athlètes par catégorie — votre catégorie est repérée.
            </div>
            <CategoryBars
              categories={summary.categories}
              total={summary.categories_total}
              highlight={participation.category ?? undefined}
            />
          </Card>
        )}
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
          className="inline-flex items-center gap-1 text-sm font-medium text-[var(--tcn-text-faint)] transition-colors hover:text-foreground"
        >
          <ChevronLeft className="size-4" />
          {link.label}
        </Link>
      ))}
    </div>
  );
}

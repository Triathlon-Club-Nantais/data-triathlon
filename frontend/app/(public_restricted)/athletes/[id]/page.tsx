import Link from "next/link";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { StatCard, MetaPill, Card, Eyebrow } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { AthleteAvatar } from "./AthleteAvatar";
import { AthleteSelection } from "./AthleteSelection";
import { EventsTable } from "./EventsTable";
import { AthleteAdminPanel } from "@/components/athletes/AthleteAdminPanel";
import { formatToken, genderShort, ordinalFr } from "@/lib/utils/format";
import { bestRatio, progressionSeries, recurringWeakSegment } from "@/lib/utils/ranking";
import { resumeAthlete } from "@/lib/utils/athlete-stats";
import { ProgressionChart } from "@/components/charts/ProgressionChart";
import { AthleteComparisonChart } from "@/components/charts/AthleteComparisonChart";

export default async function AthletePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiServer.getAthlete(Number(id)).catch(() => null);
  if (!data) notFound();
  const { athlete, participations } = data;
  const fullName = [athlete.prenom, athlete.nom].filter(Boolean).join(" ");

  // Les tuiles ne portent que sur les participations déjà validées : une saisie
  // manuelle « en attente de validation » (#270) ne doit pas fausser les KPI
  // avant qu'un bénévole ne l'ait vérifiée (#438). Le tableau détaillé plus bas,
  // lui, continue d'afficher `participations` au complet.
  // Le **régime** de tuiles, lui, suit le volume : sous 3 épreuves, les cinq
  // tuiles habituelles ne rendent que des tautologies et des tirets (#488).
  const resume = resumeAthlete(participations);
  const { validees: validated, enAttente: pendingCount } = resume;

  // La catégorie n'est pas sur l'athlète : elle vit sur la participation et
  // change avec l'âge. On prend celle de la dernière épreuve validée — la même
  // que `resumeAthlete` expose déjà, seule source de vérité pour éviter que la
  // pastille Catégorie et les tuiles Discipline/Temps décrivent deux courses
  // différentes à date égale (#488, revue finale) — et son année part en
  // `title` de la pastille pour dire de quand elle date.
  const derniereValidee = resume.derniere;
  const categorie = derniereValidee?.category ?? null;
  const anneeCategorie = derniereValidee?.course.event_date?.slice(0, 4) ?? null;

  const places = validated.map((p) => p.rank_overall).filter((r): r is number => r != null);
  const best = places.length ? Math.min(...places) : null;
  const top10 = places.filter((p) => p <= 10).length;

  // Format favori : jeton le plus fréquent.
  const formatCounts = new Map<string, number>();
  for (const p of validated) {
    const tok = formatToken(p.course.event_type, p.course.distance_km);
    if (tok !== "—") formatCounts.set(tok, (formatCounts.get(tok) ?? 0) + 1);
  }
  const favFormat = [...formatCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";

  const topRatio = bestRatio(validated);
  const progression = progressionSeries(validated);
  const weakSegment = recurringWeakSegment(validated);

  return (
    <PageShell>
      <div className="mb-7 flex flex-wrap items-start gap-5">
        <AthleteAvatar athleteId={athlete.id} name={fullName} />
        <PageHeader
          className="min-w-0 flex-1"
          backHref="/club/athletes"
          // Le `h1` de la destination dit « Athlètes par saison », mot pour
          // mot (convention posée par l'autre `backHref` du site, celui de
          // `/club/athletes` lui-même vers « Espace club ») — #488, revue UI/UX.
          backLabel="Athlètes par saison"
          // Le club en surtitre plutôt qu'un « Résultats enregistrés » qui ne
          // distinguait rien : les homonymes existent dans ce jeu de données, et
          // arrivé sur le profil on ne pouvait plus vérifier qu'on était sur le
          // bon (#488, PROF-5). Repli sur l'ancien surtitre sans club connu.
          eyebrow={athlete.club ?? "Résultats enregistrés"}
          title={fullName}
          actions={
            <>
              <AthleteSelection athlete={{ id: athlete.id, prenom: athlete.prenom, nom: athlete.nom }} />
              <AthleteAdminPanel
                athlete={{ id: athlete.id, nom: athlete.nom, prenom: athlete.prenom, club: athlete.club }}
              />
            </>
          }
        >
          {(categorie || athlete.gender) && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {categorie && (
                // L'année dans la pastille elle-même plutôt qu'en `title` :
                // un `title` sur un `<span>` non focusable est inaccessible
                // au clavier et au tactile — le motif qui a fait retirer les
                // six `title` du rail replié (#482). L'année est ce qui rend
                // la pastille honnête (une catégorie relevée il y a six ans
                // n'est plus la bonne) donc reste visible même sans survol
                // (#488, revue UI/UX).
                <MetaPill label="Catégorie">
                  {anneeCategorie ? `${categorie} (${anneeCategorie})` : categorie}
                </MetaPill>
              )}
              {athlete.gender && <MetaPill label="Genre">{genderShort(athlete.gender)}</MetaPill>}
            </div>
          )}
        </PageHeader>
      </div>

      {resume.regime === "reduit" && (
        <div className="mb-6 space-y-4">
          {/* Une seule colonne sous 640px : `.tcn-stat-value` rend 68px display
              sans clamp, et la tuile Temps ("01:02:03") force une piste à
              ~225px — en deux colonnes sous 640px la piste s'élargit au
              contenu et provoque un scroll horizontal (#488, revue finale). */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {resume.tuiles.map((t) => (
              <StatCard
                key={t.label}
                label={t.label}
                value={t.value}
                hint={t.hint}
                accent={false}
                valueFontSize={t.valueFontSize}
              />
            ))}
          </div>
          <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
            Ajouter une épreuve →
          </Link>
        </div>
      )}

      {/* Régime vide avec des participations en attente : le tableau plus bas
          montre bien des lignes, il faut donc dire pourquoi les chiffres, eux,
          sont absents. Sans participation du tout, l'`EmptyState`
          d'`EventsTable` (ETAT-3) porte déjà le message et le seul CTA. */}
      {resume.regime === "vide" && pendingCount > 0 && (
        <p className="mb-6 text-sm text-[var(--tcn-text-faint)]">
          Aucun résultat validé pour l&apos;instant — {pendingCount} en attente de validation.
        </p>
      )}

      {resume.regime === "complet" && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard
            label="Épreuves"
            value={validated.length}
            // Le tableau plus bas montre aussi les participations en attente de
            // validation (#270) : sans ce repère, un « 0 » ou un compte plus bas
            // que le nombre de lignes du tableau peut se lire comme une absence
            // de résultat plutôt que comme une validation encore à faire (#438).
            hint={pendingCount > 0 ? `${pendingCount} en attente de validation` : null}
            accent={false}
          />
          <StatCard label="Meilleure place" value={best ?? "—"} valueColor="var(--tcn-orange)" accent={false} />
          <StatCard
            label="Meilleur ratio"
            value={topRatio ? `Top ${topRatio.ratio.percent}%` : "—"}
            hint={topRatio ? `${ordinalFr(topRatio.ratio.rank)} sur ${topRatio.ratio.total}` : null}
            valueColor="var(--tcn-orange)"
            accent={false}
          />
          <StatCard label="Top 10" value={top10} accent={false} />
          <StatCard label="Format favori" value={favFormat} accent={false} />
        </div>
      )}

      {validated.length > 0 && (
        <Card style={{ marginBottom: 24 }}>
          <Eyebrow>Progression</Eyebrow>
          <ProgressionChart points={progression} />
          {weakSegment && (
            // US4 (#466) : un point faible répété, pas une contre-performance
            // isolée — d'où le seuil de majorité stricte de `recurringWeakSegment`.
            <p style={{ marginTop: 10, fontSize: 13, color: "var(--tcn-text-faint)" }}>
              Point faible récurrent : <strong>{weakSegment.label}</strong> ({weakSegment.count} épreuves
              sur {weakSegment.total}).
            </p>
          )}
        </Card>
      )}

      {validated.length > 0 && <AthleteComparisonChart mine={validated} />}

      <EventsTable participations={participations} athleteId={athlete.id} athleteName={fullName} />
    </PageShell>
  );
}

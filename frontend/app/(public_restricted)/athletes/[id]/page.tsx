import Link from "next/link";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { StatCard, MetaPill, Card, Eyebrow } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { AthleteAvatar } from "./AthleteAvatar";
import { AthleteHeaderActions } from "./AthleteHeaderActions";
import { EventsTable } from "./EventsTable";
import { SeasonValidationPanel } from "@/components/athletes/SeasonValidationPanel";
import { VolunteerActionsList } from "@/components/athletes/VolunteerActionsList";
import { formatToken, disciplineBreakdownBySeason, genderShort, ordinalFr } from "@/lib/utils/format";
import { BarList } from "@/components/charts/BarList";
import { CAT_COLORS } from "@/components/charts/CategoryBars";
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
  const disciplineBySeason = disciplineBreakdownBySeason(validated);
  // Une couleur par jeton de format, stable d'une saison à l'autre (#655) : sans
  // ça, toutes les barres de `BarList` partageaient la même teinte unique
  // (`var(--accent-ink)`, son repli sans `colorer`). L'assignation part de
  // l'ordre d'apparition, identique à chaque rendu pour un même jeu de
  // participations, donc « M » garde la même couleur d'un bloc de saison à
  // l'autre — condition nécessaire pour que la légende ci-dessous (#656) vaille
  // pour l'ensemble des blocs plutôt que pour un seul.
  const formatTokens = [...new Set(disciplineBySeason.flatMap(({ entries }) => entries.map(([key]) => key)))];
  const formatColor = new Map(formatTokens.map((tok, i) => [tok, CAT_COLORS[i % CAT_COLORS.length]]));

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
              <AthleteHeaderActions
                athlete={{ id: athlete.id, nom: athlete.nom, prenom: athlete.prenom, club: athlete.club }}
              />
              <SeasonValidationPanel
                athlete={{ id: athlete.id, nom: athlete.nom, prenom: athlete.prenom }}
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

      {/* Une seule pile Tailwind (`space-y-6`, 24px) pour l'espacement entre
          toutes les sections de la page — même système que `/club` et
          `/resultats` — plutôt que des marges inline par carte, qui avaient
          fini par diverger entre elles (#654). */}
      <div className="space-y-6">
        {resume.regime === "reduit" && (
          <div className="space-y-4">
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
          <p className="text-sm text-[var(--tcn-text-faint)]">
            Aucun résultat validé pour l&apos;instant — {pendingCount} en attente de validation.
          </p>
        )}

        {resume.regime === "complet" && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
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
          <Card>
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

        {disciplineBySeason.length > 0 && (
          <Card data-testid="repartition-saison">
            <Eyebrow>Répartition par saison</Eyebrow>
            {/* Légende posée une seule fois pour tous les blocs de saison
                ci-dessous (#656) : sans elle, les mêmes jetons de format
                (« M », « S »…) se répètent bloc après bloc sans qu'aucun repère
                commun ne dise que leur couleur est stable d'une saison à
                l'autre. `aria-hidden` : purement redondante avec le
                récapitulatif texte de chaque `BarList` (son `role="img"`), qui
                nomme déjà chaque jeton — la couleur n'y porte jamais
                l'information seule (WCAG 1.4.1). */}
            <div
              aria-hidden
              data-testid="legende-format"
              className="mb-3 mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--tcn-text-faint)]"
            >
              {formatTokens.map((tok) => (
                <span key={tok}>
                  <span style={{ color: formatColor.get(tok) }}>■</span> {tok}
                </span>
              ))}
            </div>
            <div className="space-y-5">
              {disciplineBySeason.map(({ season, entries }) => (
                <div key={season}>
                  <p className="mb-2 text-sm font-semibold text-[var(--tcn-text-faint)]">{season}</p>
                  <BarList
                    entries={entries}
                    labeller={(key) => key}
                    colorer={(key) => formatColor.get(key) ?? "var(--accent-ink)"}
                    subjectLabel="format"
                  />
                </div>
              ))}
            </div>
          </Card>
        )}

        {validated.length > 0 && <AthleteComparisonChart mine={validated} />}

        <EventsTable participations={participations} athleteId={athlete.id} athleteName={fullName} />

        <VolunteerActionsList athleteId={athlete.id} />
      </div>
    </PageShell>
  );
}

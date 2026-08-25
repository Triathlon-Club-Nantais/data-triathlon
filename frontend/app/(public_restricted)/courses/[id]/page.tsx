import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { ApiError } from "@/lib/api/client";
import { Card, Eyebrow, MetaPill } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { RaceFinishers } from "@/components/results/RaceFinishers";
import { ReliabilityMark, SplitCoverageNote } from "@/components/results/ReliabilityMark";
import { CourseSourcesPanel } from "@/components/courses/CourseSourcesPanel";
import { ClubBreakdown } from "@/components/courses/ClubBreakdown";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";
import { Histogram } from "@/components/charts/Histogram";
import { GenderDonut } from "@/components/charts/GenderDonut";
import { CategoryBars } from "@/components/charts/CategoryBars";
import { CATEGORY_PARAM, CLUB_PARAM, SCOPE_PARAM, scopeFromParam } from "@/lib/scope";
import { PAGE_SIZE_PARAM, parsePageSize } from "@/lib/pageSize";

/**
 * Convertit une épreuve absente en `null`, et **laisse remonter le reste**.
 *
 * Avaler toute erreur ferait afficher « épreuve introuvable » sur un backend en
 * panne ou injoignable : indiscernable d'un lien mort pour le visiteur, et
 * invisible en supervision. Le risque a doublé avec la synthèse, qui est un
 * second appel — une panne de cette seule route ferait disparaître en 404 des
 * pages parfaitement valides.
 */
function rendreNullSi404(erreur: unknown): null {
  if (erreur instanceof ApiError && erreur.status === 404) return null;
  throw erreur;
}

/**
 * Titres qui **disent leur portée** (#486, RES-7).
 *
 * « Répartition par catégorie » et « Top clubs » laissaient croire à un tout, alors que
 * les deux cartes ne montrent qu'un extrait — huit catégories, neuf clubs. Le titre
 * redevient exact dès qu'il nomme le nombre affiché, et reste sobre quand la liste est
 * complète : il n'y a alors rien à restreindre.
 */
function titreCategories(
  affichees: number,
  total: number,
  categories: { count: number }[],
): string {
  const couvertes = categories.reduce((somme, c) => somme + c.count, 0);
  if (couvertes >= total) return "Répartition par catégorie";
  return `Les ${affichees} catégories les plus représentées`;
}

function titreClubs(affiches: number, total: number): string {
  if (total <= affiches) return "Top clubs";
  return `Les ${affiches} clubs les plus représentés`;
}

/** Numéro de page lu dans l'URL : absent, illisible ou < 1 vaut 1, sans erreur. */
function parsePage(raw: string | undefined): number {
  const n = Number(raw);
  return Number.isInteger(n) && n >= 1 ? n : 1;
}

export default async function CoursePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const page = parsePage(sp.page);
  const q = sp.q?.trim() || undefined;
  const scope = scopeFromParam(sp[SCOPE_PARAM]);
  // Liste blanche : le sélecteur du classement ne sait représenter que quatre
  // tailles, une URL bricolée le désaccorderait (cf. `lib/pageSize.ts`).
  const pageSize = parsePageSize(sp[PAGE_SIZE_PARAM]);

  // Trois appels distincts, et c'est structurant : la synthèse porte sur
  // l'épreuve entière, le classement sur la sélection courante. Chercher un nom
  // ne doit pas faire tomber l'histogramme à une barre (#163). Les sources ne
  // conditionnent jamais le 404 : une épreuve sans source migrée reste une
  // épreuve valide (#284), elle n'affiche simplement aucun chip.
  // Filtres venus des cartes de synthèse (#486). Transmis verbatim : l'API
  // compare en égalité exacte au libellé que la carte a elle-même proposé.
  const club = sp[CLUB_PARAM]?.trim() || undefined;
  const category = sp[CATEGORY_PARAM]?.trim() || undefined;

  /** Lien vers le classement filtré, les autres paramètres d'URL conservés. */
  function lienFiltre(cle: string, valeur: string): string {
    const params = new URLSearchParams(
      Object.entries(sp).filter(([, v]) => v != null) as [string, string][],
    );
    params.set(cle, valeur);
    // Une sélection réduite atterrirait sinon sur une page vide.
    params.delete("page");
    return `/courses/${id}?${params.toString()}`;
  }

  const [data, summary, sources] = await Promise.all([
    apiServer
      .getCourse(Number(id), { page, page_size: pageSize, q, scope, club, category })
      .catch(rendreNullSi404),
    apiServer.getCourseSummary(Number(id)).catch(rendreNullSi404),
    apiServer.getCourseSources(Number(id)).catch(rendreNullSi404),
  ]);
  if (!data || !summary) notFound();
  const { course, participations } = data;

  const { total, finishers, dnf, dns, dsq, unknown, tcn_count: tcnCount } = summary;

  // ── Répartition genre ──
  const genderTotal = summary.male + summary.female;
  const hasGender = genderTotal > 0;
  const malePct = hasGender ? (summary.male / genderTotal) * 100 : 0;
  const femalePct = hasGender ? (summary.female / genderTotal) * 100 : 0;

  // ── Top clubs ──
  // Le drapeau TCN vient du backend, seul dépositaire de la définition (#76).
  const clubs = summary.clubs;

  return (
    <PageShell>
      <div style={{ marginBottom: 24 }}>
        <Eyebrow style={{ marginBottom: 6 }}>Résultats complets</Eyebrow>
        <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(30px, 5vw, 46px)", fontWeight: 400, color: "var(--tcn-ink)", lineHeight: 1, margin: 0, marginBottom: 12 }}>{formatEventName(course.name, course.is_relay)}</h1>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <MetaPill label="Type">{eventTypeLabel(course.event_type)}</MetaPill>
          <MetaPill label="Format">{formatToken(course.event_type, course.distance_km)}</MetaPill>
          {course.event_date && <MetaPill label="Date">{formatDate(course.event_date)}</MetaPill>}
          <MetaPill label="Participants">{total}</MetaPill>
          <MetaPill label="Finishers">{finishers}</MetaPill>
          {dnf > 0 && <MetaPill label="Abandons">{dnf}</MetaPill>}
          {dns > 0 && <MetaPill label="Non-partants">{dns}</MetaPill>}
          {dsq > 0 && <MetaPill label="Disqualifiés">{dsq}</MetaPill>}
          {unknown > 0 && <MetaPill label="Indéterminés">{unknown}</MetaPill>}
          {tcnCount > 0 && <MetaPill accent dot>{tcnCount} athlète{tcnCount > 1 ? "s" : ""} TCN</MetaPill>}
          <ReliabilityMark isReliable={course.is_reliable} issues={course.quality_issues} />
          <CourseSourcesPanel courseId={course.id} initialSources={sources ?? []} />
        </div>
        <SplitCoverageNote median={summary.split_gap_median} />
      </div>

      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card padding={24} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, fontWeight: 400, color: "var(--tcn-ink)", margin: 0, alignSelf: "flex-start" }}>Répartition genre</h2>
          <GenderDonut malePct={malePct} femalePct={femalePct} hasGender={hasGender} />
        </Card>

        <Card padding={24}>
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, fontWeight: 400, color: "var(--tcn-ink)", margin: 0, marginBottom: 18 }}>{titreCategories(summary.categories.length, summary.categories_total, summary.categories)}</h2>
          <CategoryBars
            categories={summary.categories}
            total={summary.categories_total}
            hrefFor={(nom) => lienFiltre(CATEGORY_PARAM, nom)}
          />
        </Card>

        <Card padding={24} className="sm:col-span-2 lg:col-span-1">
          {/* `aria-labelledby` : l'écran porte deux tableaux (celui-ci et le
              classement). Sans nom, un lecteur d'écran les annonce tous deux
              « tableau » sans dire lequel. */}
          <h2 id="titre-top-clubs" style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, fontWeight: 400, color: "var(--tcn-ink)", margin: 0, marginBottom: 14 }}>{titreClubs(clubs.length, summary.clubs_total)}</h2>
          <ClubBreakdown
            clubs={clubs}
            total={summary.clubs_total}
            hrefFor={(nom) => lienFiltre(CLUB_PARAM, nom)}
          />
        </Card>
      </div>

      {summary.histogram && (
        <Card padding={28} style={{ marginBottom: 18 }}>
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0, marginBottom: 4 }}>Distribution des temps des finishers</h2>
          <div style={{ fontSize: 13, color: "var(--tcn-text-muted)", marginBottom: 18 }}>Nombre d&apos;athlètes par tranche de 5 minutes</div>
          <Histogram
            bars={summary.histogram.bars}
            max={Math.max(...summary.histogram.bars)}
            startSec={summary.histogram.start_sec}
            bucketSec={summary.histogram.bucket_sec}
          />
        </Card>
      )}

      <RaceFinishers
        participations={participations}
        summary={summary}
        total={data.total}
        page={data.page}
        pageSize={data.page_size}
        eventType={course.event_type}
      />
    </PageShell>
  );
}


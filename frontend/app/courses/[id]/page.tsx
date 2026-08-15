import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { ApiError } from "@/lib/api/client";
import { Card, Eyebrow, MetaPill } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { RaceFinishers } from "@/components/results/RaceFinishers";
import { CourseSourcesPanel } from "@/components/courses/CourseSourcesPanel";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";
import { Histogram } from "@/components/charts/Histogram";
import { GenderDonut } from "@/components/charts/GenderDonut";
import { SCOPE_PARAM, scopeFromParam } from "@/lib/scope";

const CAT_COLORS = [
  "var(--tcn-orange)", "var(--tcn-orange-300)", "var(--tcn-ink)", "var(--tcn-ink-2)",
  "var(--tcn-ink-3)", "var(--tcn-grey-400)", "var(--tcn-orange-200)", "var(--tcn-grey-300)",
];

function pctFr(pct: number): string {
  return pct.toFixed(1).replace(".", ",");
}

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

  // Trois appels distincts, et c'est structurant : la synthèse porte sur
  // l'épreuve entière, le classement sur la sélection courante. Chercher un nom
  // ne doit pas faire tomber l'histogramme à une barre (#163). Les sources ne
  // conditionnent jamais le 404 : une épreuve sans source migrée reste une
  // épreuve valide (#284), elle n'affiche simplement aucun chip.
  const [data, summary, sources] = await Promise.all([
    apiServer.getCourse(Number(id), { page, q, scope }).catch(rendreNullSi404),
    apiServer.getCourseSummary(Number(id)).catch(rendreNullSi404),
    apiServer.getCourseSources(Number(id)),
  ]);
  if (!data || !summary) notFound();
  const { course, participations } = data;

  const { total, finishers, dnf, dns, dsq, unknown, tcn_count: tcnCount } = summary;

  // ── Répartition genre ──
  const genderTotal = summary.male + summary.female;
  const hasGender = genderTotal > 0;
  const malePct = hasGender ? (summary.male / genderTotal) * 100 : 0;
  const femalePct = hasGender ? (summary.female / genderTotal) * 100 : 0;

  // ── Répartition par catégorie ──
  // Dénominateur : toutes les catégories, pas les 8 affichées (cf. `categories_total`).
  const catTotal = summary.categories_total;
  const categories = summary.categories.map((c, i) => ({
    name: c.name,
    pct: catTotal ? (c.count / catTotal) * 100 : 0,
    color: CAT_COLORS[i % CAT_COLORS.length],
  }));

  // ── Top clubs ──
  // Le drapeau TCN vient du backend, seul dépositaire de la définition (#76).
  const clubs = summary.clubs;

  return (
    <PageShell>
      <div style={{ marginBottom: 24 }}>
        <Eyebrow style={{ marginBottom: 6 }}>Résultats complets</Eyebrow>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(30px, 5vw, 46px)", color: "var(--tcn-ink)", lineHeight: 1, marginBottom: 12 }}>{formatEventName(course.name, course.is_relay)}</div>
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
          <CourseSourcesPanel courseId={course.id} initialSources={sources} />
        </div>
      </div>

      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card padding={24} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, color: "var(--tcn-ink)", alignSelf: "flex-start" }}>Répartition genre</div>
          <GenderDonut malePct={malePct} femalePct={femalePct} hasGender={hasGender} />
        </Card>

        <Card padding={24}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, color: "var(--tcn-ink)", marginBottom: 18 }}>Répartition par catégorie</div>
          {categories.length === 0 ? (
            <div style={{ color: "var(--tcn-text-faint)", fontSize: 14 }}>Catégories non renseignées.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {categories.map((c) => (
                <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ flex: "none", width: 36, fontWeight: 800, fontSize: 13, color: "var(--tcn-ink)" }}>{c.name}</span>
                  <div style={{ flex: 1, height: 13, background: "var(--tcn-fill)", borderRadius: 999, overflow: "hidden" }}>
                    <div style={{ width: c.pct + "%", height: "100%", background: c.color, borderRadius: 999 }} />
                  </div>
                  <span style={{ flex: "none", width: 48, textAlign: "right", fontSize: 13, fontWeight: 700, color: "var(--tcn-text-body)" }}>{pctFr(c.pct)}%</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card padding={24} className="sm:col-span-2 lg:col-span-1">
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, color: "var(--tcn-ink)", marginBottom: 14 }}>Top clubs</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10, paddingBottom: 8, fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)", marginBottom: 4 }}>
            <div>Club</div><div style={{ textAlign: "right" }}>Athlètes</div>
          </div>
          {clubs.length === 0 ? (
            <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, paddingTop: 8 }}>Clubs non renseignés.</div>
          ) : (
            clubs.map(({ name, count, is_tcn: own }) => {
              return (
                <div key={name} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10, padding: "7px 0", borderBottom: "1px solid var(--tcn-border-faint2)" }}>
                  <div style={{ fontSize: 13, fontWeight: own ? 700 : 600, color: own ? "var(--tcn-orange)" : "var(--tcn-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{name}</div>
                  <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 16, color: own ? "var(--tcn-orange)" : "var(--tcn-ink)", textAlign: "right" }}>{count}</div>
                </div>
              );
            })
          )}
        </Card>
      </div>

      {summary.histogram && (
        <Card padding={28} style={{ marginBottom: 18 }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", marginBottom: 4 }}>Distribution des temps des finishers</div>
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


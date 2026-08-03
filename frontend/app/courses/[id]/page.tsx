import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { ApiError } from "@/lib/api/client";
import { Card, Eyebrow, MetaPill } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { RaceFinishers } from "@/components/results/RaceFinishers";
import { eventTypeLabel, providerLabel } from "@/lib/constants";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";
import { buildTicks, formatTickLabel } from "@/lib/utils/histogram-ticks";
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

  // Deux appels distincts, et c'est structurant : la synthèse porte sur
  // l'épreuve entière, le classement sur la sélection courante. Chercher un nom
  // ne doit pas faire tomber l'histogramme à une barre (#163).
  const [data, summary] = await Promise.all([
    apiServer.getCourse(Number(id), { page, q, scope }).catch(rendreNullSi404),
    apiServer.getCourseSummary(Number(id)).catch(rendreNullSi404),
  ]);
  if (!data || !summary) notFound();
  const { course, participations } = data;

  const { total, finishers, non_finishers: nonFinishers, unknown, tcn_count: tcnCount } = summary;

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
          <MetaPill label="Partants">{total}</MetaPill>
          <MetaPill label="Finishers">{finishers}</MetaPill>
          {nonFinishers > 0 && <MetaPill label="Abandons">{nonFinishers}</MetaPill>}
          {unknown > 0 && <MetaPill label="Indéterminés">{unknown}</MetaPill>}
          {tcnCount > 0 && <MetaPill accent dot>{tcnCount} athlète{tcnCount > 1 ? "s" : ""} TCN</MetaPill>}
          {course.source_url && (
            <MetaPill label="Source" href={course.source_url} title="Ouvrir les résultats du chronométreur dans un nouvel onglet">
              {providerLabel(course.provider)}
              <span aria-hidden="true">↗</span>
            </MetaPill>
          )}
        </div>
      </div>

      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card padding={24} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, color: "var(--tcn-ink)", alignSelf: "flex-start" }}>Répartition genre</div>
          <div style={{ position: "relative", width: 130, height: 130, borderRadius: 999, background: hasGender ? `conic-gradient(var(--tcn-orange) 0 ${malePct}%, var(--tcn-ink) ${malePct}% 100%)` : "var(--tcn-grey-300)" }}>
            <div style={{ position: "absolute", inset: 26, borderRadius: 999, background: "var(--tcn-surface)", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
              <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", lineHeight: 1 }}>{Math.round(malePct)}%</div>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", color: "var(--tcn-text-faint)", letterSpacing: ".05em" }}>Hommes</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
            <Legend color="var(--tcn-orange)" label="Homme" value={`${pctFr(malePct)}%`} />
            <Legend color="var(--tcn-ink)" label="Femme" value={`${pctFr(femalePct)}%`} />
          </div>
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

function Legend({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
      <span style={{ width: 10, height: 10, borderRadius: 3, background: color }} />
      <span style={{ color: "var(--tcn-text-body)" }}>{label}</span>
      <b style={{ marginLeft: "auto", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>{value}</b>
    </div>
  );
}

function Histogram({
  bars,
  max,
  startSec,
  bucketSec,
}: {
  bars: number[];
  max: number;
  startSec: number;
  bucketSec: number;
}) {
  const W = 900;
  const H = 240; // +20px par rapport à l'ancien 220 pour loger les labels X
  const top = 20;
  const bottom = 190;
  const left = 46;
  const usableW = W - left - 10;
  const barGap = usableW / bars.length;
  const barW = Math.max(4, barGap * 0.72);
  const yTicks = 5;

  // Fin de la fenêtre temporelle = bord droit du dernier bucket. Les ticks X
  // sont calculés en secondes, puis projetés sur X via barGap / bucketSec.
  const endSec = startSec + bars.length * bucketSec;
  const xTicks = bars.length > 0 ? buildTicks(startSec, endSec) : [];
  const secToX = (sec: number) => left + ((sec - startSec) / bucketSec) * barGap;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {/* Axe Y — ticks horizontaux + labels de comptage. */}
      {Array.from({ length: yTicks + 1 }, (_, i) => {
        const v = Math.round((max / yTicks) * i);
        const y = bottom - (i / yTicks) * (bottom - top);
        return (
          <g key={i}>
            <line x1={left - 6} y1={y} x2={W - 10} y2={y} stroke="var(--tcn-border-faint)" />
            <text x={left - 14} y={y + 4} textAnchor="end" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{v}</text>
          </g>
        );
      })}
      {/* Barres. */}
      {bars.map((c, i) => {
        const h = max ? (c / max) * (bottom - top) : 0;
        return <rect key={i} x={left + i * barGap} y={bottom - h} width={barW} height={h} rx="2" fill="var(--tcn-orange)" />;
      })}
      {/* Axe X — lignes verticales (fines, comme les horizontales de l'axe Y)
          + labels d'heure `H:MM` alignés sur des multiples ronds du pas (#129). */}
      {xTicks.map((tickSec) => {
        const x = secToX(tickSec);
        return (
          <g key={tickSec}>
            <line x1={x} y1={top} x2={x} y2={bottom} stroke="var(--tcn-border-faint)" />
            <text x={x} y={bottom + 16} textAnchor="middle" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{formatTickLabel(tickSec)}</text>
          </g>
        );
      })}
    </svg>
  );
}

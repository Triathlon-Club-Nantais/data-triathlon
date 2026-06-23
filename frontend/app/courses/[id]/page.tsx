import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { Card, Eyebrow, MetaPill } from "@/components/tcn";
import { RaceFinishers } from "@/components/results/RaceFinishers";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import { isTCN } from "@/lib/utils/club";

const CAT_COLORS = [
  "var(--tcn-orange)", "var(--tcn-orange-300)", "var(--tcn-ink)", "var(--tcn-ink-2)",
  "var(--tcn-ink-3)", "var(--tcn-grey-400)", "var(--tcn-orange-200)", "var(--tcn-grey-300)",
];

function parseSeconds(t: string | null | undefined): number | null {
  if (!t) return null;
  const m = String(t).match(/(?:(\d+):)?(\d{1,2}):(\d{2})$/);
  if (!m) return null;
  return (+(m[1] ?? 0)) * 3600 + +m[2] * 60 + +m[3];
}

function pctFr(pct: number): string {
  return pct.toFixed(1).replace(".", ",");
}

export default async function CoursePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiServer.getCourse(Number(id)).catch(() => null);
  if (!data) notFound();
  const { course, participations } = data;
  const total = participations.length;
  const tcnCount = participations.filter((p) => isTCN(p.club)).length;

  // ── Répartition genre ──
  let male = 0;
  let female = 0;
  for (const p of participations) {
    const c = (p.athlete?.gender ?? "").trim().toLowerCase()[0];
    if (c === "f" || c === "w") female += 1;
    else if (c === "m" || c === "h") male += 1;
  }
  const genderTotal = male + female;
  const malePct = genderTotal ? (male / genderTotal) * 100 : 0;

  // ── Répartition par catégorie ──
  const catMap = new Map<string, number>();
  for (const p of participations) {
    const cat = p.category?.trim();
    if (cat) catMap.set(cat, (catMap.get(cat) ?? 0) + 1);
  }
  const catTotal = [...catMap.values()].reduce((a, b) => a + b, 0);
  const categories = [...catMap.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([name, count], i) => ({ name, pct: catTotal ? (count / catTotal) * 100 : 0, color: CAT_COLORS[i % CAT_COLORS.length] }));

  // ── Top clubs ──
  const clubMap = new Map<string, number>();
  for (const p of participations) {
    const club = p.club?.trim();
    if (club) clubMap.set(club, (clubMap.get(club) ?? 0) + 1);
  }
  const clubs = [...clubMap.entries()].sort((a, b) => b[1] - a[1]).slice(0, 9);

  // ── Histogramme des temps (5 min) ──
  const secs = participations.map((p) => parseSeconds(p.total_time)).filter((s): s is number => s != null);
  const hist = buildHistogram(secs);

  return (
    <div style={{ maxWidth: "var(--tcn-content-max)", margin: "0 auto", padding: "36px 40px 64px" }}>
      <div style={{ marginBottom: 24 }}>
        <Eyebrow style={{ marginBottom: 6 }}>Résultats complets</Eyebrow>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 46, color: "var(--tcn-ink)", lineHeight: 1, marginBottom: 12 }}>{course.name}</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          <MetaPill label="Type">{eventTypeLabel(course.event_type)}</MetaPill>
          <MetaPill label="Format">{formatToken(course.event_type, course.distance_km)}</MetaPill>
          {course.event_date && <MetaPill label="Date">{formatDate(course.event_date)}</MetaPill>}
          <MetaPill label="Finishers">{total}</MetaPill>
          {tcnCount > 0 && <MetaPill accent dot>{tcnCount} athlète{tcnCount > 1 ? "s" : ""} TCN</MetaPill>}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr 260px", gap: 18, marginBottom: 18 }}>
        <Card padding={24} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, color: "var(--tcn-ink)", alignSelf: "flex-start" }}>Répartition genre</div>
          <div style={{ position: "relative", width: 130, height: 130, borderRadius: 999, background: `conic-gradient(var(--tcn-orange) 0 ${malePct}%, var(--tcn-ink) ${malePct}% 100%)` }}>
            <div style={{ position: "absolute", inset: 26, borderRadius: 999, background: "var(--tcn-surface)", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
              <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", lineHeight: 1 }}>{Math.round(malePct)}%</div>
              <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", color: "var(--tcn-text-faint)", letterSpacing: ".05em" }}>Hommes</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
            <Legend color="var(--tcn-orange)" label="Homme" value={`${pctFr(malePct)}%`} />
            <Legend color="var(--tcn-ink)" label="Femme" value={`${pctFr(100 - malePct)}%`} />
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

        <Card padding={24}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 18, color: "var(--tcn-ink)", marginBottom: 14 }}>Top clubs</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 10, paddingBottom: 8, fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)", marginBottom: 4 }}>
            <div>Club</div><div style={{ textAlign: "right" }}>Athlètes</div>
          </div>
          {clubs.length === 0 ? (
            <div style={{ color: "var(--tcn-text-faint)", fontSize: 13, paddingTop: 8 }}>Clubs non renseignés.</div>
          ) : (
            clubs.map(([name, count]) => {
              const own = isTCN(name);
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

      {hist.bars.length > 0 && (
        <Card padding={28} style={{ marginBottom: 18 }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)", marginBottom: 4 }}>Distribution des temps des finishers</div>
          <div style={{ fontSize: 13, color: "var(--tcn-text-muted)", marginBottom: 18 }}>Nombre d&apos;athlètes par tranche de 5 minutes</div>
          <Histogram bars={hist.bars} max={hist.max} />
        </Card>
      )}

      <RaceFinishers participations={participations} tcnCount={tcnCount} />
    </div>
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

function buildHistogram(secs: number[]): { bars: number[]; max: number } {
  if (secs.length === 0) return { bars: [], max: 0 };
  const BUCKET = 300;
  const minB = Math.floor(Math.min(...secs) / BUCKET);
  const maxB = Math.floor(Math.max(...secs) / BUCKET);
  const n = Math.min(maxB - minB + 1, 60);
  const bars = new Array(n).fill(0);
  for (const s of secs) {
    const idx = Math.min(Math.floor(s / BUCKET) - minB, n - 1);
    bars[idx] += 1;
  }
  return { bars, max: Math.max(...bars) };
}

function Histogram({ bars, max }: { bars: number[]; max: number }) {
  const W = 900;
  const H = 220;
  const top = 20;
  const bottom = 190;
  const left = 46;
  const usableW = W - left - 10;
  const barGap = usableW / bars.length;
  const barW = Math.max(4, barGap * 0.72);
  const ticks = 5;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {Array.from({ length: ticks + 1 }, (_, i) => {
        const v = Math.round((max / ticks) * i);
        const y = bottom - (i / ticks) * (bottom - top);
        return (
          <g key={i}>
            <line x1={left - 6} y1={y} x2={W - 10} y2={y} stroke="var(--tcn-border-faint)" />
            <text x={left - 14} y={y + 4} textAnchor="end" fontSize="11" fill="var(--tcn-text-faint)" fontFamily="Barlow">{v}</text>
          </g>
        );
      })}
      {bars.map((c, i) => {
        const h = max ? (c / max) * (bottom - top) : 0;
        return <rect key={i} x={left + i * barGap} y={bottom - h} width={barW} height={h} rx="2" fill="var(--tcn-orange)" />;
      })}
    </svg>
  );
}

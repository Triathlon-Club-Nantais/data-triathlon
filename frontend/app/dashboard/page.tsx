import Link from "next/link";
import { apiServer } from "@/lib/api/server";
import { clubFromScope } from "@/lib/scope";
import { ScopeToggle } from "@/components/layout/ScopeToggle";
import { StatCard, Card, Eyebrow, FormatChip } from "@/components/tcn";
import { aggregateDisciplines, formatToken, pctFr } from "@/lib/utils/format";
import { isPodium } from "@/lib/utils/club-aggregate";

const TrophyIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 4h12v3a6 6 0 0 1-12 0V4z" /><path d="M6 5H3v2a3 3 0 0 0 3 3" /><path d="M18 5h3v2a3 3 0 0 1-3 3" /><path d="M9 17h6" /><path d="M12 13v4" /><path d="M8 21h8" /></svg>
);
const PodiumIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="4" width="6" height="17" /><rect x="2" y="10" width="6" height="11" /><rect x="16" y="8" width="6" height="13" /></svg>
);
const Top10Icon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--tcn-orange)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="9" r="6" /><path d="M12 6v3l2 1" /><path d="M9 14l-2 7 5-3 5 3-2-7" /></svg>
);

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const club = clubFromScope(sp.scope);

  const [stats, eventsPage, participations] = await Promise.all([
    apiServer.getStats(club),
    apiServer.listEvents({ club, page_size: 200 }),
    apiServer.listParticipations({ club, page_size: 2000 }),
  ]);

  const victoires = participations.filter((p) => p.rank_overall === 1).length;
  const podiums = participations.filter(isPodium).length;
  const top10 = participations.filter((p) => p.rank_overall != null && p.rank_overall <= 10).length;

  const disciplines = aggregateDisciplines(stats.by_type);
  const topEvents = [...eventsPage.items].sort((a, b) => b.total - a.total).slice(0, 6);

  return (
    <div style={{ maxWidth: "var(--tcn-content-max)", margin: "0 auto", padding: "36px 40px 64px" }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 16, flexWrap: "wrap", marginBottom: 26 }}>
        <div>
          <Eyebrow>Participations aux courses</Eyebrow>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 40, color: "var(--tcn-ink)", lineHeight: 1, marginTop: 6 }}>Saison 2025 — 2026</div>
          <div style={{ fontSize: 15, color: "var(--tcn-text-muted)", marginTop: 8, fontWeight: 500 }}>Vue d&apos;ensemble des performances des athlètes du club</div>
        </div>
        <ScopeToggle />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr 1fr", gap: 18, marginBottom: 18 }}>
        <StatCard variant="hero" label="Dossards enregistrés" value={stats.total.toLocaleString("fr-FR")} delta={`${stats.athletes} athlètes · ${stats.events} épreuves`} />
        <StatCard label="Victoires" value={victoires} icon={<TrophyIcon />} />
        <StatCard label="Podiums" value={podiums} icon={<PodiumIcon />} />
        <StatCard label="Top 10" value={top10} icon={<Top10Icon />} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.25fr", gap: 18 }}>
        <Card>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 24, color: "var(--tcn-ink)", marginBottom: 20 }}>Type d&apos;épreuves</div>
          {disciplines.length === 0 ? (
            <div style={{ color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucune épreuve enregistrée.</div>
          ) : (
            <>
              <div style={{ display: "flex", height: 20, borderRadius: 999, overflow: "hidden", marginBottom: 24 }}>
                {disciplines.map((d) => <div key={d.name} style={{ width: d.pct + "%", background: d.color }} />)}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {disciplines.map((d) => (
                  <div key={d.name} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 15, color: "var(--tcn-text-body)" }}>
                    <span style={{ width: 12, height: 12, borderRadius: 3, background: d.color }} />{d.name}
                    <b style={{ marginLeft: "auto", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>{pctFr(d.pct)}%</b>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 24, color: "var(--tcn-ink)", marginBottom: 18 }}>Épreuves préférées</div>
          <div style={{ display: "grid", gridTemplateColumns: "24px 1fr auto auto", gap: "0 14px", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", paddingBottom: 10, borderBottom: "1px solid var(--tcn-border)" }}>
            <div>#</div><div>Épreuve</div><div>Format</div><div style={{ textAlign: "right" }}>Dossards</div>
          </div>
          {topEvents.map((e, i) => (
            <Link key={e.id} href={`/courses/${e.id}`} className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: "24px 1fr auto auto", gap: "0 14px", alignItems: "center", padding: "12px 0", borderBottom: i < topEvents.length - 1 ? "1px solid var(--tcn-border-faint)" : "none", fontSize: 15 }}>
              <span style={{ fontFamily: "var(--tcn-font-display)", color: i === 0 ? "var(--tcn-orange)" : "var(--tcn-text-muted)" }}>{i + 1}</span>
              <span style={{ color: "var(--tcn-ink)", fontWeight: 600 }}>{e.event_name}</span>
              <FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip>
              <b style={{ textAlign: "right", fontFamily: "var(--tcn-font-display)", color: "var(--tcn-ink)" }}>{e.total}</b>
            </Link>
          ))}
          {topEvents.length === 0 && <div style={{ padding: 20, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucune épreuve.</div>}
        </Card>
      </div>
    </div>
  );
}

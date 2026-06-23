import Link from "next/link";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { Avatar, StatCard, Card, Eyebrow, FormatChip, PlaceBadge } from "@/components/tcn";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import { recentParticipations } from "@/lib/utils/club-aggregate";

const COLS = "120px 1fr 150px 90px 120px 90px 28px";

export default async function AthletePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiServer.getAthlete(Number(id)).catch(() => null);
  if (!data) notFound();
  const { athlete, participations } = data;
  const fullName = [athlete.prenom, athlete.nom].filter(Boolean).join(" ");

  const places = participations.map((p) => p.rank_overall).filter((r): r is number => r != null);
  const best = places.length ? Math.min(...places) : null;
  const top10 = places.filter((p) => p <= 10).length;

  // Format favori : jeton le plus fréquent.
  const formatCounts = new Map<string, number>();
  for (const p of participations) {
    const tok = formatToken(p.course?.event_type, p.course?.distance_km);
    if (tok !== "—") formatCounts.set(tok, (formatCounts.get(tok) ?? 0) + 1);
  }
  const favFormat = [...formatCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";

  const ordered = recentParticipations(participations, participations.length);

  return (
    <div style={{ maxWidth: "var(--tcn-content-max)", margin: "0 auto", padding: "36px 40px 64px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 28 }}>
        <Avatar name={fullName} size={72} />
        <div>
          <Eyebrow>Résultats enregistrés</Eyebrow>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 42, color: "var(--tcn-ink)", lineHeight: 1, marginTop: 4 }}>{fullName}</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 18, marginBottom: 24 }}>
        <StatCard label="Épreuves" value={participations.length} accent={false} />
        <StatCard label="Meilleure place" value={best ?? "—"} valueColor="var(--tcn-orange)" accent={false} />
        <StatCard label="Top 10" value={top10} accent={false} />
        <StatCard label="Format favori" value={favFormat} accent={false} />
      </div>

      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 26px 16px" }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>Toutes les épreuves</div>
          <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", fontWeight: 600 }}>Clique sur une épreuve pour voir le détail →</div>
        </div>
        {ordered.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucun résultat pour cet athlète.</div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: COLS, gap: "0 18px", padding: "0 26px 12px", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
              <div>Date</div><div>Épreuve</div><div>Type</div><div>Format</div><div>Temps final</div><div>Place</div><div></div>
            </div>
            {ordered.map((p) => (
              <Link key={p.id} href={`/courses/${p.course?.id}`} className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: COLS, gap: "0 18px", alignItems: "center", padding: "15px 26px", borderBottom: "1px solid var(--tcn-border-faint)" }}>
                <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>{formatDate(p.course?.event_date)}</div>
                <div style={{ fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}>{p.course?.name}</div>
                <div style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>{eventTypeLabel(p.course?.event_type)}</div>
                <div><FormatChip>{formatToken(p.course?.event_type, p.course?.distance_km)}</FormatChip></div>
                <div style={{ fontSize: 15, color: "var(--tcn-ink)", fontFamily: "var(--tcn-font-cond)", fontWeight: 700 }}>{p.total_time ?? "—"}</div>
                <div>{p.rank_overall != null ? <PlaceBadge place={p.rank_overall} /> : <span style={{ color: "var(--tcn-text-faint)" }}>—</span>}</div>
                <div style={{ textAlign: "right", color: "var(--tcn-text-disabled)", fontSize: 16 }}>→</div>
              </Link>
            ))}
          </>
        )}
      </Card>
    </div>
  );
}

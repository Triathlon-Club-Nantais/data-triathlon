import Link from "next/link";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { Avatar, StatCard, Card, Eyebrow, FormatChip, PlaceBadge } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken, ordinalFr } from "@/lib/utils/format";
import { bestRatio, rankRatio } from "@/lib/utils/ranking";
import { describeQualityIssues } from "@/lib/quality";
import { formatDate } from "@/lib/utils/date";
import { recentParticipations } from "@/lib/utils/club-aggregate";
import { gridColumns, gridMinWidth, type Track } from "@/lib/utils/table";

// Date | Épreuve | Type | Format | Temps final | Place | →
// La colonne Place loge la pastille *et* le « /N » de classés (issue #80).
const TRACKS: Track[] = [120, { flexMin: 200 }, 150, 90, 120, 120, 28];

// Tooltip d'une course non fiable : détail des anomalies quand connues, repli
// générique sinon (ancien import backfillé sans quality_issues).
function unreliableTooltip(issues: Record<string, number> | null | undefined): string {
  const details = describeQualityIssues(issues);
  if (details.length === 0) return "Fiabilité des données incertaine chez le chronométreur — le classement complet ne peut pas être affiché.";
  return `Fiabilité incertaine : ${details.join(" ; ")}.`;
}
const GAP = 18;
const PADDING_X = 26;
const COLS = gridColumns(TRACKS);
const MIN_WIDTH = gridMinWidth(TRACKS, { gap: GAP, paddingX: PADDING_X });

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

  const topRatio = bestRatio(participations);

  const ordered = recentParticipations(participations, participations.length);

  return (
    <PageShell>
      <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 28, flexWrap: "wrap" }}>
        <Avatar name={fullName} size={72} />
        <div>
          <Eyebrow>Résultats enregistrés</Eyebrow>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(28px, 5vw, 42px)", color: "var(--tcn-ink)", lineHeight: 1, marginTop: 4 }}>{fullName}</div>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Épreuves" value={participations.length} accent={false} />
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

      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 26px 16px", flexWrap: "wrap", gap: 8 }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>Toutes les épreuves</div>
          <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", fontWeight: 600 }}>Clique sur une épreuve pour voir le détail →</div>
        </div>
        {ordered.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucun résultat pour cet athlète.</div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <div style={{ minWidth: MIN_WIDTH }}>
              <div style={{ display: "grid", gridTemplateColumns: COLS, columnGap: GAP, padding: `0 ${PADDING_X}px 12px`, fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
                <div>Date</div><div>Épreuve</div><div>Type</div><div>Format</div><div>Temps final</div><div>Place</div><div></div>
              </div>
              {ordered.map((p) => {
                const { ratio, reason } = rankRatio(p);
                const unreliableTitle =
                  reason === "unreliable" ? unreliableTooltip(p.course?.quality_issues) : null;
                return (
                  <Link key={p.id} href={`/courses/${p.course?.id}`} className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: COLS, columnGap: GAP, alignItems: "center", padding: `15px ${PADDING_X}px`, borderBottom: "1px solid var(--tcn-border-faint)" }}>
                    <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>{formatDate(p.course?.event_date)}</div>
                    <div style={{ fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700 }}>{p.course?.name}</div>
                    <div style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>{eventTypeLabel(p.course?.event_type)}</div>
                    <div><FormatChip>{formatToken(p.course?.event_type, p.course?.distance_km)}</FormatChip></div>
                    <div style={{ fontSize: 15, color: "var(--tcn-ink)", fontFamily: "var(--tcn-font-cond)", fontWeight: 700 }}>{p.total_time ?? "—"}</div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                      {p.rank_overall != null ? (
                        <>
                          <PlaceBadge place={p.rank_overall} />
                          {ratio ? (
                            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--tcn-text-faint)" }}>
                              /{ratio.total}
                            </span>
                          ) : null}
                          {unreliableTitle ? (
                            <span
                              data-testid="unreliable-marker"
                              title={unreliableTitle}
                              aria-label={unreliableTitle}
                              // `role="img"` : le texte est purement informatif, pas un contrôle.
                              role="img"
                              style={{ fontSize: 13, color: "var(--tcn-text-faint)", cursor: "help", userSelect: "none" }}
                            >
                              ⚠
                            </span>
                          ) : null}
                        </>
                      ) : (
                        <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                      )}
                    </div>
                    <div style={{ textAlign: "right", color: "var(--tcn-text-disabled)", fontSize: 16 }}>→</div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </Card>
    </PageShell>
  );
}

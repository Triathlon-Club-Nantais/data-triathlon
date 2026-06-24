import Link from "next/link";
import { apiServer } from "@/lib/api/server";
import { Card, Eyebrow, FormatChip, Badge } from "@/components/tcn";
import { TcnScrapeForm } from "@/components/scrape/TcnScrapeForm";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";

const RCOLS = "140px 1fr 90px 130px";

export default async function AjouterPage() {
  const events = await apiServer.listEvents({ page_size: 6, sort: "date_desc" }).catch(() => null);
  const recent = events?.items ?? [];

  return (
    <div style={{ maxWidth: "var(--tcn-content-form)", margin: "0 auto", padding: "40px 40px 80px" }}>
      <Eyebrow style={{ marginBottom: 6 }}>Nouvelle participation</Eyebrow>
      <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 44, color: "var(--tcn-ink)", lineHeight: 1, marginBottom: 30 }}>Ajouter un triathlon</div>

      <TcnScrapeForm />

      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ padding: "22px 28px 16px", borderBottom: "1px solid var(--tcn-border)", display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>Derniers résultats enregistrés</div>
          <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", fontWeight: 600 }}>Clique pour voir la page de résultats →</div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: RCOLS, gap: "0 14px", padding: "12px 24px", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
          <div>Date</div><div>Épreuve</div><div>Format</div><div>Athlètes club</div>
        </div>
        {recent.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--tcn-text-faint)", fontSize: 14 }}>Aucun résultat enregistré pour l&apos;instant.</div>
        ) : (
          recent.map((e) => (
            <Link key={e.id} href={`/courses/${e.id}`} className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: RCOLS, gap: "0 14px", alignItems: "center", padding: "13px 24px", borderBottom: "1px solid var(--tcn-border-faint)" }}>
              <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>{formatDate(e.event_date)}</div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "var(--tcn-ink)" }}>{e.event_name}</div>
              <div><FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip></div>
              <div>{e.tcn_count > 0 ? <Badge count>{e.tcn_count}</Badge> : <span style={{ color: "var(--tcn-text-faint)", fontSize: 13 }}>—</span>}</div>
            </Link>
          ))
        )}
      </Card>
    </div>
  );
}

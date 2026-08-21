import Link from "next/link";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { Card, Eyebrow, FormatChip, Badge } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { EmptyState } from "@/components/ui/empty-state";
import { TcnScrapeForm } from "@/components/scrape/TcnScrapeForm";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";

const RCOLS = "140px 1fr 90px 130px";

export default async function AjouterPage() {
  // « Derniers résultats enregistrés » (#201) : tri par date d'import, pas par
  // date d'épreuve, sans quoi une épreuve ancienne qu'on vient d'importer
  // resterait invisible sous 6 épreuves à venir déjà en base. Fenêtre de
  // revalidation courte (#376) : ce lien est prefetché en continu par le
  // bouton « + » de la navigation globale, présent sur toutes les pages.
  const events = await apiServer
    .listEvents({ page_size: 6, sort: "imported_desc" }, { revalidateSeconds: SHORT_REVALIDATE_SECONDS })
    .catch(() => null);
  const recent = events?.items ?? [];

  return (
    <PageShell form>
      <Eyebrow style={{ marginBottom: 6 }}>Nouvelle participation</Eyebrow>
      <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(30px, 6vw, 44px)", fontWeight: 400, color: "var(--tcn-ink)", lineHeight: 1, margin: 0, marginBottom: 30 }}>Ajouter une épreuve</h1>

      <TcnScrapeForm />

      <Card padding={0} style={{ overflow: "hidden" }}>
        <div style={{ padding: "22px 28px 16px", borderBottom: "1px solid var(--tcn-border)", display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>Derniers résultats enregistrés</h2>
          <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", fontWeight: 600 }}>Clique pour voir la page de résultats →</div>
        </div>
        <div style={{ overflowX: "auto" }}>
          <div style={{ minWidth: 480 }}>
            <div style={{ display: "grid", gridTemplateColumns: RCOLS, gap: "0 14px", padding: "12px 24px", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
              <div>Date</div><div>Épreuve</div><div>Format</div><div>Athlètes club</div>
            </div>
            {recent.length === 0 ? (
              // Pas d'action : le formulaire d'import est juste au-dessus.
              <EmptyState bare title="Aucun résultat enregistré pour l'instant" />
            ) : (
              recent.map((e) => (
                <Link key={e.id} href={`/courses/${e.id}`} className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: RCOLS, gap: "0 14px", alignItems: "center", padding: "13px 24px", borderBottom: "1px solid var(--tcn-border-faint)" }}>
                  <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>{formatDate(e.event_date)}</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "var(--tcn-ink)" }}>{formatEventName(e.event_name, e.is_relay)}</div>
                  <div><FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip></div>
                  <div>{e.tcn_count > 0 ? <Badge count>{e.tcn_count}</Badge> : <span style={{ color: "var(--tcn-text-faint)", fontSize: 13 }}>—</span>}</div>
                </Link>
              ))
            )}
          </div>
        </div>
      </Card>
    </PageShell>
  );
}

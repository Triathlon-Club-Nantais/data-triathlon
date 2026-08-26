import Link from "next/link";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { Card, Eyebrow, FormatChip, Badge, LigneCarte } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { EmptyState } from "@/components/ui/empty-state";
import { TcnScrapeForm } from "@/components/scrape/TcnScrapeForm";
import { formatToken } from "@/lib/utils/format";
import { formatDate } from "@/lib/utils/date";
import { formatEventName } from "@/lib/utils/event";

const RCOLS = "140px 1fr 90px 130px";

/**
 * Ce que la grille et les cartes lisent identiquement par ligne — un seul
 * calcul, pour que les deux arbres ne puissent pas diverger en silence
 * (#461, leçon de la tâche 5 : une carte sans membre du club ne rendait
 * rien là où la grille rendait un tiret).
 */
function compteurClub(tcnCount: number) {
  return tcnCount > 0 ? (
    <Badge count>{tcnCount}</Badge>
  ) : (
    <span style={{ color: "var(--tcn-text-faint)", fontSize: 13 }}>—</span>
  );
}

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
        <div
          data-testid="recents-grille"
          data-affichage="grille"
          // Le cran Tailwind `sm:` (640) reste sous les autres écrans du lot :
          // 480 (grille) + CHROME_RAIL_REPLIE (157, `lib/utils/table.ts`) = 637,
          // sous 640 par 3px — vérifié en revue UI/UX #461. Marge fine à
          // resurveiller si `RCOLS` s'élargit.
          className="hidden sm:block overflow-x-auto"
          role="region"
          aria-label="Derniers résultats enregistrés, défilement horizontal"
          tabIndex={0}
        >
          <div style={{ minWidth: 480 }}>
            <table className="tcn-table" role="table">
              <thead role="rowgroup">
                <tr role="row" style={{ display: "grid", gridTemplateColumns: RCOLS, gap: "0 14px", padding: "12px 24px", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--tcn-text-faint)", borderBottom: "1px solid var(--tcn-border)" }}>
                  <th role="columnheader" scope="col">Date</th><th role="columnheader" scope="col">Épreuve</th><th role="columnheader" scope="col">Format</th><th role="columnheader" scope="col">Athlètes club</th>
                </tr>
              </thead>
              <tbody role="rowgroup">
                {recent.map((e) => (
                  <tr key={e.id} role="row" className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: RCOLS, gap: "0 14px", alignItems: "center", padding: "13px 24px", borderBottom: "1px solid var(--tcn-border-faint)" }}>
                    <td role="cell" style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>{formatDate(e.event_date)}</td>
                    <td role="cell" style={{ fontSize: 15, fontWeight: 700, color: "var(--tcn-ink)" }}>
                      <Link href={`/courses/${e.id}`} className="tcn-rowlink__cible">{formatEventName(e.event_name, e.is_relay)}</Link>
                    </td>
                    <td role="cell"><FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip></td>
                    <td role="cell">{compteurClub(e.tcn_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {recent.length === 0 && (
              // Pas d'action : le formulaire d'import est juste au-dessus.
              // Hors du tableau : posé en ligne, il s'annoncerait comme une
              // donnée du classement (#481, contrat C1).
              <EmptyState bare title="Aucun résultat enregistré pour l'instant" />
            )}
          </div>
        </div>

        {/* Sous 640 px, les 480 px de la grille dépassent la largeur utile
            d'un iPhone SE, gouttière `PageShell` déduite (#461). */}
        <div data-testid="recents-cartes" data-affichage="cartes" className="sm:hidden">
          {recent.length === 0 ? (
            // Pas d'action : le formulaire d'import est juste au-dessus.
            <EmptyState bare title="Aucun résultat enregistré pour l'instant" />
          ) : (
            recent.map((e) => (
              <LigneCarte
                key={e.id}
                href={`/courses/${e.id}`}
                surtitre={formatDate(e.event_date)}
                titre={formatEventName(e.event_name, e.is_relay)}
                valeur={compteurClub(e.tcn_count)}
                meta={<FormatChip>{formatToken(e.event_type, e.distance_km)}</FormatChip>}
              />
            ))
          )}
        </div>
      </Card>
    </PageShell>
  );
}

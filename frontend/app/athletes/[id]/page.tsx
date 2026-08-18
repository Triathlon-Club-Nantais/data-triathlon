import { Fragment } from "react";
import Link from "next/link";
import { Eye } from "lucide-react";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { Avatar, StatCard, Card, Eyebrow, FormatChip, PlaceBadge, PendingBadge } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { SelectAthleteButton } from "./SelectAthleteButton";
import { eventTypeLabel } from "@/lib/constants";
import { formatToken, ordinalFr } from "@/lib/utils/format";
import { bestRatio, rankRatio } from "@/lib/utils/ranking";
import { describeQualityIssues } from "@/lib/quality";
import { formatDate } from "@/lib/utils/date";
import { recentParticipations } from "@/lib/utils/club-aggregate";
import { isNonFinisher } from "@/lib/utils/raceOrder";
import { isHttpUrl } from "@/lib/utils/url";
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

  // Les 5 StatCard ne portent que sur les participations déjà validées : une
  // saisie manuelle « en attente de validation » (#270) ne doit pas fausser
  // les KPI avant qu'un bénévole ne l'ait vérifiée (#438). Le tableau détaillé
  // plus bas, lui, continue d'afficher `participations` au complet.
  const validated = participations.filter((p) => !p.is_pending_validation);

  const places = validated.map((p) => p.rank_overall).filter((r): r is number => r != null);
  const best = places.length ? Math.min(...places) : null;
  const top10 = places.filter((p) => p <= 10).length;

  // Format favori : jeton le plus fréquent.
  const formatCounts = new Map<string, number>();
  for (const p of validated) {
    const tok = formatToken(p.course?.event_type, p.course?.distance_km);
    if (tok !== "—") formatCounts.set(tok, (formatCounts.get(tok) ?? 0) + 1);
  }
  const favFormat = [...formatCounts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—";

  const topRatio = bestRatio(validated);

  const ordered = recentParticipations(participations, participations.length);

  return (
    <PageShell>
      <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 28, flexWrap: "wrap" }}>
        <Avatar name={fullName} size={72} />
        <div>
          <Eyebrow>Résultats enregistrés</Eyebrow>
          <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(28px, 5vw, 42px)", color: "var(--tcn-ink)", lineHeight: 1, marginTop: 4 }}>{fullName}</div>
        </div>
        <div style={{ marginLeft: "auto" }}>
          <SelectAthleteButton athlete={{ id: athlete.id, prenom: athlete.prenom, nom: athlete.nom }} />
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Épreuves" value={validated.length} accent={false} />
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
                const { ratio } = rankRatio(p);
                // AC5 : le marqueur ⚠ dépend de la fiabilité de la course, pas
                // du rang ni du statut. Il doit apparaître à côté d'un DNF non
                // fiable comme à côté d'un finisher classé.
                const unreliableTitle =
                  p.course?.is_reliable === false
                    ? unreliableTooltip(p.course?.quality_issues)
                    : null;
                const nonFinisher = isNonFinisher(p.status);
                const sigle = (p.status ?? "").toUpperCase();
                return (
                  <Fragment key={p.id}>
                  <Link href={`/courses/${p.course?.id}/participations/${p.id}`} className="tcn-rowlink" style={{ display: "grid", gridTemplateColumns: COLS, columnGap: GAP, alignItems: "center", padding: `15px ${PADDING_X}px`, borderBottom: p.is_pending_validation || (p.evidence_url && isHttpUrl(p.evidence_url)) ? "none" : "1px solid var(--tcn-border-faint)" }}>
                    <div style={{ fontSize: 14, color: "var(--tcn-text-muted)", fontWeight: 600 }}>{formatDate(p.course?.event_date)}</div>
                    <div style={{ fontSize: 15, color: "var(--tcn-ink)", fontWeight: 700, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      {p.course?.name}
                      {p.is_pending_validation && <PendingBadge />}
                    </div>
                    <div style={{ fontSize: 14, color: "var(--tcn-text-body)" }}>{eventTypeLabel(p.course?.event_type)}</div>
                    <div><FormatChip>{formatToken(p.course?.event_type, p.course?.distance_km)}</FormatChip></div>
                    <div style={{ fontSize: 15, color: "var(--tcn-ink)", fontFamily: "var(--tcn-font-cond)", fontWeight: 700 }}>{p.total_time ?? "—"}</div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                      {nonFinisher ? (
                        // Non-finisher : sigle sobre. DSQ garde le rang entre
                        // parenthèses quand le chronométreur en a fourni un ;
                        // le /N n'est ajouté que si la course est fiable.
                        <span style={{ fontSize: 14, fontWeight: 700, color: "var(--tcn-text-muted)" }}>
                          {sigle}
                          {p.rank_overall != null ? (
                            <>({p.rank_overall}{ratio ? `/${ratio.total}` : ""})</>
                          ) : null}
                        </span>
                      ) : p.rank_overall != null ? (
                        <>
                          <PlaceBadge place={p.rank_overall} />
                          {ratio ? (
                            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--tcn-text-faint)" }}>
                              /{ratio.total}
                            </span>
                          ) : null}
                        </>
                      ) : (
                        <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                      )}
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
                    </div>
                    <div style={{ textAlign: "right", color: "var(--tcn-text-disabled)", fontSize: 16 }}>→</div>
                  </Link>
                  {p.evidence_url && isHttpUrl(p.evidence_url) ? (
                    // Ligne séparée, hors du `<Link>` de la ligne : un `<a>`
                    // imbriqué dans un autre serait invalide en HTML. Le texte
                    // qui n'est pas une URL http(s) exploitable reste stocké
                    // (cas limite de la spec) mais n'est jamais rendu cliquable.
                    <div style={{ padding: `0 ${PADDING_X}px 12px`, borderBottom: "1px solid var(--tcn-border-faint)" }}>
                      <a
                        href={p.evidence_url}
                        target="_blank"
                        rel="noreferrer"
                        // Affordance de bouton discret : classes partagées avec
                        // `tcn/Button` (voir globals.css) plutôt qu'un composant
                        // dédié — un `<button>` serait sémantiquement faux ici,
                        // c'est une navigation, pas une action (rôle "link" à
                        // conserver, cf. page.test.tsx). `--secondary` et non
                        // `--ghost` : cette carte a un fond blanc
                        // (`--tcn-surface`), sur lequel le remplissage et la
                        // bordure de `--ghost` tombent sous 1,3:1 (WCAG
                        // 1.4.11) — quasi invisibles, à l'inverse de
                        // l'affordance recherchée. La bordure encre de
                        // `--secondary` reste à ~16:1 sur ce même fond.
                        className="tcn-btn tcn-btn--sm tcn-btn--secondary"
                      >
                        <Eye size={14} aria-hidden="true" />
                        Voir la preuve
                      </a>
                    </div>
                  ) : null}
                  </Fragment>
                );
              })}
            </div>
          </div>
        )}
      </Card>
    </PageShell>
  );
}

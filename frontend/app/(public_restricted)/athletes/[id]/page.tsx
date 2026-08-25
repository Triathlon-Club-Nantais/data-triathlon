import Link from "next/link";
import { notFound } from "next/navigation";
import { apiServer } from "@/lib/api/server";
import { StatCard, Eyebrow } from "@/components/tcn";
import { PageShell } from "@/components/layout/PageShell";
import { AthleteAvatar } from "./AthleteAvatar";
import { AthleteSelection } from "./AthleteSelection";
import { EventsTable } from "./EventsTable";
import { AthleteAdminPanel } from "@/components/athletes/AthleteAdminPanel";
import { formatToken, ordinalFr } from "@/lib/utils/format";
import { bestRatio } from "@/lib/utils/ranking";
import { resumeAthlete } from "@/lib/utils/athlete-stats";

export default async function AthletePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await apiServer.getAthlete(Number(id)).catch(() => null);
  if (!data) notFound();
  const { athlete, participations } = data;
  const fullName = [athlete.prenom, athlete.nom].filter(Boolean).join(" ");

  // Les tuiles ne portent que sur les participations déjà validées : une saisie
  // manuelle « en attente de validation » (#270) ne doit pas fausser les KPI
  // avant qu'un bénévole ne l'ait vérifiée (#438). Le tableau détaillé plus bas,
  // lui, continue d'afficher `participations` au complet.
  // Le **régime** de tuiles, lui, suit le volume : sous 3 épreuves, les cinq
  // tuiles habituelles ne rendent que des tautologies et des tirets (#488).
  const resume = resumeAthlete(participations);
  const { validees: validated, enAttente: pendingCount } = resume;

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

  return (
    <PageShell>
      <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 28, flexWrap: "wrap" }}>
        <AthleteAvatar athleteId={athlete.id} name={fullName} />
        <div>
          <Eyebrow>Résultats enregistrés</Eyebrow>
          <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(28px, 5vw, 42px)", fontWeight: 400, color: "var(--tcn-ink)", lineHeight: 1, margin: 0, marginTop: 4 }}>{fullName}</h1>
        </div>
        {/* Un seul `marginLeft: "auto"` pour les deux commandes : un second
            les séparerait aux deux bouts de la ligne. Sur mobile, l'en-tête
            passe à la ligne — elles y restent côte à côte. */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <AthleteSelection athlete={{ id: athlete.id, prenom: athlete.prenom, nom: athlete.nom }} />
          <AthleteAdminPanel
            athlete={{ id: athlete.id, nom: athlete.nom, prenom: athlete.prenom, club: athlete.club }}
          />
        </div>
      </div>

      {resume.regime === "reduit" && (
        <div className="mb-6 space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {resume.tuiles.map((t) => (
              <StatCard key={t.label} label={t.label} value={t.value} hint={t.hint} accent={false} />
            ))}
          </div>
          <Link href="/ajouter" className="text-sm font-semibold text-accent-ink hover:underline">
            Ajouter une épreuve →
          </Link>
        </div>
      )}

      {/* Régime vide avec des participations en attente : le tableau plus bas
          montre bien des lignes, il faut donc dire pourquoi les chiffres, eux,
          sont absents. Sans participation du tout, l'`EmptyState`
          d'`EventsTable` (ETAT-3) porte déjà le message et le seul CTA. */}
      {resume.regime === "vide" && pendingCount > 0 && (
        <p className="mb-6 text-sm text-[var(--tcn-text-faint)]">
          Aucun résultat validé pour l&apos;instant — {pendingCount} en attente de validation.
        </p>
      )}

      {resume.regime === "complet" && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard
            label="Épreuves"
            value={validated.length}
            // Le tableau plus bas montre aussi les participations en attente de
            // validation (#270) : sans ce repère, un « 0 » ou un compte plus bas
            // que le nombre de lignes du tableau peut se lire comme une absence
            // de résultat plutôt que comme une validation encore à faire (#438).
            hint={pendingCount > 0 ? `${pendingCount} en attente de validation` : null}
            accent={false}
          />
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
      )}

      <EventsTable participations={participations} athleteId={athlete.id} athleteName={fullName} />
    </PageShell>
  );
}

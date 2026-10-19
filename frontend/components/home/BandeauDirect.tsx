import type { CSSProperties } from "react";
import { Card } from "@/components/tcn/Card";
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";
import { estToutRecent, moisDeSaison, titreSortie } from "@/lib/home";
import type { ClubLastOuting, Stats } from "@/lib/types";
import { formatCount, motCompte } from "@/lib/utils/format";
import { seasonLabel, seasonSelectionLabel } from "@/lib/utils/season";
import { ChiffreAnime } from "./ChiffreAnime";

const display = { fontFamily: "var(--tcn-font-display)", fontWeight: 400, lineHeight: 1 } as const;

function Chiffre({ valeur, libelle }: { valeur: number; libelle: string }) {
  return (
    <div style={{ color: "var(--tcn-ink)" }}>
      <div style={{ ...display, fontSize: 28 }}>{formatCount(valeur)}</div>
      <div style={{ fontSize: 13, fontWeight: 700 }}>{libelle}</div>
    </div>
  );
}

function Histogramme({ stats, seasons }: { stats: Stats; seasons: number[] }) {
  const season = Math.max(...seasons);
  const mois = moisDeSaison(stats.by_month, season);
  const max = Math.max(1, ...mois.map((m) => m.valeur));
  const resume = mois.filter((m) => m.valeur > 0).map((m) => `${m.libelle} : ${m.valeur}`).join(", ");
  return (
    <figure role="img" aria-label={`Résultats par mois. ${resume || "Aucun pour l'instant"}.`} style={{ margin: 0 }}>
      <div aria-hidden="true" style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 72 }}>
        {mois.map((m, i) => (
          <span key={m.mois} className="tcn-barre" style={{ "--i": i, flex: 1, height: `${Math.max(4, (m.valeur / max) * 100)}%`, borderRadius: 3, background: m.valeur ? "var(--tcn-orange)" : "var(--tcn-grey-300)" } as CSSProperties} />
        ))}
      </div>
      <figcaption aria-hidden="true" style={{ fontSize: 12, fontWeight: 700, marginTop: 6, color: "var(--tcn-text-muted)" }}>
        Résultats par mois{seasons.length > 1 && ` · ${seasonLabel(season)}`}
      </figcaption>
    </figure>
  );
}

/** Le pouls du club en tête d'accueil (#1621) : carte de la dernière sortie, carte de la saison. */
export function BandeauDirect({ sortie, stats, seasons, today }: { sortie: ClubLastOuting | null; stats: Stats; seasons: number[]; today: Date }) {
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <section
        aria-label="Dernière sortie"
        className="tcn-carte-sortie"
        style={{ minWidth: 0, background: "var(--tcn-orange-grad)", color: "#fff", borderRadius: "var(--tcn-radius-xl)", padding: "24px clamp(18px, 4vw, 32px)", boxShadow: "var(--tcn-shadow-orange-lg)" }}
      >
        {sortie ? (
          <>
            <p style={{ margin: 0, fontWeight: 800, display: "flex", alignItems: "center", gap: 10 }}>
              {titreSortie(sortie.end_date, today)}
              {estToutRecent(sortie.end_date, today) && <span aria-hidden="true" className="tcn-pouls" />}
            </p>
            <p style={{ ...display, margin: "6px 0 0", fontSize: "clamp(40px, 9vw, 64px)" }}>
              <ChiffreAnime valeur={sortie.athletes} /> {CLUB_NAME_SHORT}
            </p>
            <p style={{ margin: "6px 0 0", fontWeight: 700 }}>
              {motCompte(sortie.events, "épreuve")} · {motCompte(sortie.podiums, "podium")}
            </p>
          </>
        ) : (
          <p style={{ ...display, margin: 0, fontSize: 28 }}>Pas encore d&apos;épreuve cette saison</p>
        )}
      </section>
      <section aria-labelledby="bandeau-saison-titre" style={{ minWidth: 0 }}>
        <Card padding="24px clamp(18px, 4vw, 32px)" style={{ height: "100%", minWidth: 0 }}>
          <h1 id="bandeau-saison-titre" style={{ margin: 0, fontSize: 12, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--tcn-text-muted)" }}>
            {CLUB_NAME} · {seasonSelectionLabel(seasons)}
          </h1>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 16 }}>
            <Chiffre valeur={stats.total} libelle="résultats" />
            <Chiffre valeur={stats.athletes} libelle="athlètes" />
            <Chiffre valeur={stats.rank_counters.all.podiums} libelle="podiums" />
          </div>
          <div style={{ marginTop: 20 }}>
            <Histogramme stats={stats} seasons={seasons} />
          </div>
        </Card>
      </section>
    </div>
  );
}

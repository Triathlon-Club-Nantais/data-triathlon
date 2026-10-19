import type { CSSProperties } from "react";
import { Card } from "@/components/tcn/Card";
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";
import { estToutRecent, moisComparesParSaison, titreSortie } from "@/lib/home";
import type { ClubLastOuting, Stats } from "@/lib/types";
import { formatCount, motCompte } from "@/lib/utils/format";
import { currentSeason, seasonAbsenceLabel, seasonLabel, seasonSelectionLabel } from "@/lib/utils/season";
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

const COULEURS_SERIES = ["var(--tcn-text-faint)", "var(--tcn-ink)", "var(--tcn-orange)"];

function Histogramme({ stats, seasons }: { stats: Stats; seasons: number[] }) {
  const { saisons, tronque, mois } = moisComparesParSaison(stats.by_month, seasons);
  const couleurs = COULEURS_SERIES.slice(-saisons.length);
  const compare = saisons.length > 1;
  const max = Math.max(1, ...mois.flatMap((m) => m.valeurs));
  const resume = saisons
    .map((saison, k) => {
      const valeurs = mois.filter((m) => m.valeurs[k] > 0).map((m) => `${m.libelle} : ${m.valeurs[k]}`).join(", ");
      return `${compare ? `${seasonLabel(saison)} : ` : ""}${valeurs || "Aucun pour l'instant"}`;
    })
    .join(". ");
  return (
    <figure role="img" aria-label={`Résultats par mois. ${resume}.`} style={{ margin: 0 }}>
      <div aria-hidden="true" style={{ display: "flex", gap: compare ? 6 : 4 }}>
        {mois.map((m) => (
          <div key={m.index} style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 1, height: 72 }}>
              {m.valeurs.map((valeur, k) => (
                <span
                  key={saisons[k]}
                  className="tcn-barre"
                  title={`${m.libelle} : ${valeur}`}
                  style={{ "--i": m.index, flex: 1, minWidth: 0, height: `${Math.max(4, (valeur / max) * 100)}%`, borderRadius: 3, background: valeur ? couleurs[k] : "var(--tcn-grey-300)" } as CSSProperties}
                />
              ))}
            </div>
            <div style={{ marginTop: 4, textAlign: "center", fontSize: 11, color: "var(--tcn-text-muted)" }}>
              <span className="hidden sm:inline">{m.libelle}</span>
              <span className="sm:hidden">{m.libelle[0].toUpperCase()}</span>
            </div>
          </div>
        ))}
      </div>
      <figcaption aria-hidden="true" style={{ fontSize: 12, fontWeight: 700, marginTop: 6, color: "var(--tcn-text-muted)" }}>
        Résultats par mois
        {compare && (
          <span style={{ display: "flex", flexWrap: "wrap", gap: "2px 12px", marginTop: 4 }}>
            {saisons.map((saison, k) => (
              <span key={saison} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: couleurs[k] }} />
                {seasonLabel(saison)}
              </span>
            ))}
          </span>
        )}
        {tronque && <span style={{ display: "block", fontWeight: 400 }}>3 saisons les plus récentes</span>}
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
        style={{ minWidth: 0, background: "var(--tcn-orange-grad)", color: "#fff", borderRadius: "var(--tcn-radius-3xl)", padding: "24px clamp(18px, 4vw, 32px)", boxShadow: "var(--tcn-shadow-orange-lg)" }}
      >
        <div className="tcn-carte-sortie-contenu">
        {sortie ? (
          <>
            <h2 style={{ margin: 0, fontSize: "inherit", fontWeight: 800, display: "flex", alignItems: "center", gap: 10 }}>
              {titreSortie(sortie.end_date, today)}
              {estToutRecent(sortie.end_date, today) && <span aria-hidden="true" className="tcn-pouls" />}
            </h2>
            <p style={{ ...display, margin: "6px 0 0", fontSize: "clamp(40px, 9vw, 64px)" }}>
              <ChiffreAnime valeur={sortie.athletes} /> {CLUB_NAME_SHORT}
            </p>
            <p style={{ margin: "6px 0 0", fontWeight: 700 }}>
              {motCompte(sortie.events, "épreuve")} · {motCompte(sortie.podiums, "podium")}
            </p>
          </>
        ) : (
          <p style={{ ...display, margin: 0, fontSize: 28 }}>{seasons.length === 1 && seasons[0] === currentSeason() ? "Pas encore d'épreuve cette saison" : `Aucune épreuve pour ${seasonAbsenceLabel(seasons)}`}</p>
        )}
        </div>
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

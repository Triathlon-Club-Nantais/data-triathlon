import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";
import { moisDeSaison, titreSortie } from "@/lib/home";
import type { ClubLastOuting, Stats } from "@/lib/types";
import { formatCount, motCompte } from "@/lib/utils/format";
import { seasonLabel, seasonSelectionLabel } from "@/lib/utils/season";
import { ChiffreAnime } from "./ChiffreAnime";

const display = { fontFamily: "var(--tcn-font-display)", fontWeight: 400, lineHeight: 1 } as const;

function Chiffre({ valeur, libelle }: { valeur: number; libelle: string }) {
  return (
    <div>
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
        {mois.map((m) => (
          <span key={m.mois} style={{ flex: 1, height: `${Math.max(4, (m.valeur / max) * 100)}%`, borderRadius: 3, background: m.valeur ? "rgba(255,255,255,.9)" : "rgba(255,255,255,.25)" }} />
        ))}
      </div>
      <figcaption aria-hidden="true" style={{ fontSize: 12, fontWeight: 700, marginTop: 6 }}>
        Résultats par mois{seasons.length > 1 && ` · ${seasonLabel(season)}`}
      </figcaption>
    </figure>
  );
}

/** Le pouls du club en tête d'accueil (#1621) : dernière sortie, saison, mois. */
export function BandeauDirect({ sortie, stats, seasons, today }: { sortie: ClubLastOuting | null; stats: Stats; seasons: number[]; today: Date }) {
  return (
    <section
      aria-labelledby="bandeau-direct-titre"
      style={{ background: "var(--tcn-orange-grad)", color: "#fff", borderRadius: "var(--tcn-radius-xl)", padding: "24px clamp(18px, 4vw, 32px)", boxShadow: "var(--tcn-shadow-orange-lg)" }}
    >
      <h1 id="bandeau-direct-titre" style={{ margin: 0, fontSize: 12, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase" }}>
        {CLUB_NAME} · {seasonSelectionLabel(seasons)}
      </h1>
      <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] md:items-end">
        <div>
          {sortie ? (
            <>
              <p style={{ margin: 0, fontWeight: 800 }}>{titreSortie(sortie.end_date, today)}</p>
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
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 20 }}>
            <Chiffre valeur={stats.total} libelle="résultats" />
            <Chiffre valeur={stats.athletes} libelle="athlètes" />
            <Chiffre valeur={stats.rank_counters.all.podiums} libelle="podiums" />
          </div>
        </div>
        <Histogramme stats={stats} seasons={seasons} />
      </div>
    </section>
  );
}

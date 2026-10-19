import type { CSSProperties } from "react";
import { moisComparesParSaison } from "@/lib/home";
import { currentSeason, seasonLabel } from "@/lib/utils/season";

const COULEURS_SERIES = ["var(--tcn-text-faint)", "var(--tcn-ink)", "var(--tcn-orange)"];

/** Mois de septembre à août, jusqu'à trois saisons côte à côte ; `titre` nomme ce qu'on compte. */
export function HistogrammeMois({ byMonth, seasons, titre = "Résultats par mois" }: { byMonth: Record<string, number>; seasons: number[]; titre?: string }) {
  const { saisons, tronque, mois } = moisComparesParSaison(byMonth, seasons);
  const couleurs = COULEURS_SERIES.slice(-saisons.length);
  const compare = saisons.length > 1;
  const max = Math.max(1, ...mois.flatMap((m) => m.valeurs));
  const resume = saisons
    .map((saison, k) => {
      const valeurs = mois.filter((m) => m.valeurs[k] > 0).map((m) => `${m.libelle} : ${m.valeurs[k]}`).join(", ");
      return `${compare ? `${seasonLabel(saison)} : ` : ""}${valeurs || (saison === currentSeason() ? "Aucun pour l'instant" : "Aucun résultat")}`;
    })
    .join(". ");
  return (
    <figure role="img" aria-label={`${titre}. ${resume}.${tronque ? " Seules les 3 saisons les plus récentes sont comparées." : ""}`} style={{ margin: 0 }}>
      <div aria-hidden="true" style={{ display: "flex", gap: compare ? 6 : 4 }}>
        {mois.map((m) => (
          <div key={m.index} style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 1, height: 72 }}>
              {m.valeurs.map((valeur, k) => (
                <span
                  key={saisons[k]}
                  className="tcn-barre"
                  title={`${compare ? `${seasonLabel(saisons[k])} · ` : ""}${m.libelle} : ${valeur}`}
                  style={{ "--i": m.index, flex: 1, minWidth: 0, height: `${Math.max(4, (valeur / max) * 100)}%`, borderRadius: 3, background: valeur ? couleurs[k] : "var(--tcn-grey-300)" } as CSSProperties}
                />
              ))}
            </div>
            <div style={{ marginTop: 4, textAlign: "center", fontSize: 11, color: "var(--tcn-text-muted)" }}>
              <span className="hidden sm:inline md:hidden lg:inline">{m.libelle}</span>
              <span className="sm:hidden md:inline lg:hidden">{m.libelle[0].toUpperCase()}</span>
            </div>
          </div>
        ))}
      </div>
      <figcaption aria-hidden="true" style={{ fontSize: 12, fontWeight: 700, marginTop: 6, color: "var(--tcn-text-muted)" }}>
        {titre}
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
        {tronque && <span style={{ display: "block", fontWeight: 400 }}>Seules les 3 saisons les plus récentes sont comparées.</span>}
      </figcaption>
    </figure>
  );
}

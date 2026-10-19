import { ProgressionChart } from "@/components/charts/ProgressionChart";
import { HistogrammeMois } from "@/components/charts/HistogrammeMois";
import { Card } from "@/components/tcn";
import type { Participation } from "@/lib/types";
import { motCompte } from "@/lib/utils/format";
import { progressionSeries } from "@/lib/utils/ranking";

const titre = { fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 } as const;

/** Onglet Progression de Mon espace (#1698) : classement relatif face à la saison précédente, épreuves par mois. */
export function OngletProgression({ courant, precedent, seasons }: { courant: Participation[]; precedent: Participation[] | null; seasons: number[] }) {
  const validees = courant.filter((p) => !p.is_pending_validation);
  const valideesPrecedent = precedent?.filter((p) => !p.is_pending_validation);
  const nonFiables = [...validees, ...(valideesPrecedent ?? [])].filter((p) => p.course.is_reliable === false).length;
  const serie = progressionSeries(validees);
  const comparaison = valideesPrecedent ? progressionSeries(valideesPrecedent) : undefined;
  const parMois: Record<string, number> = {};
  for (const p of validees) {
    const mois = p.course.event_date?.slice(0, 7);
    if (mois) parMois[mois] = (parMois[mois] ?? 0) + 1;
  }

  return (
    <div className="space-y-6">
      <Card>
        <h2 style={titre}>Ma progression</h2>
        <div style={{ marginTop: 12 }}>
          <ProgressionChart points={serie} comparaison={comparaison} nonFiables={nonFiables} />
        </div>
        {serie.length >= 3 && comparaison && comparaison.length >= 2 && (
          <p style={{ marginTop: 8, fontSize: 13, color: "var(--tcn-text-muted)" }}>Trait plein : cette saison. Trait pointillé : la saison précédente.</p>
        )}
        {nonFiables > 0 && (
          <p style={{ marginTop: 8, fontSize: 13, color: "var(--tcn-text-muted)" }}>
            {motCompte(nonFiables, "épreuve")} non {nonFiables > 1 ? "fiables absentes" : "fiable absente"} de la courbe, faute de classement sûr.
          </p>
        )}
      </Card>
      <Card>
        <h2 style={titre}>Mon rythme</h2>
        <div style={{ marginTop: 12 }}>
          <HistogrammeMois byMonth={parMois} seasons={seasons} titre="Mes épreuves par mois" />
        </div>
      </Card>
    </div>
  );
}

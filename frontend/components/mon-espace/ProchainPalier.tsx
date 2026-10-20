import { Card, Eyebrow } from "@/components/tcn";
import type { Palier } from "@/lib/mon-espace";

const MOTS = { epreuves: ["épreuve", "épreuves"], podiums: ["podium", "podiums"] } as const;

/** Objectif implicite : égaler sa meilleure saison, masqué une fois atteint (#1700). */
export function ProchainPalier({ palier }: { palier: Palier | null }) {
  if (palier === null) return null;
  const fait = palier.cible - palier.reste;
  return (
    <Card padding={20}>
      <Eyebrow>Prochain palier</Eyebrow>
      <p style={{ margin: "12px 0 8px", fontSize: 15 }}>
        Encore {palier.reste} {MOTS[palier.type][palier.reste > 1 ? 1 : 0]} pour égaler votre meilleure saison
      </p>
      <div
        role="progressbar"
        aria-label="Progression vers votre meilleure saison"
        aria-valuemin={0}
        aria-valuemax={palier.cible}
        aria-valuenow={fait}
        style={{ height: 8, borderRadius: 4, background: "var(--tcn-paper)", overflow: "hidden" }}
      >
        <div style={{ width: `${(fait / palier.cible) * 100}%`, height: "100%", background: "var(--tcn-orange-deep)" }} />
      </div>
    </Card>
  );
}

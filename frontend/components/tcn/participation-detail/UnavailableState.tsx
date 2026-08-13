import Link from "next/link";
// Imports directs plutôt que via le barrel `@/components/tcn` : celui-ci
// réexporte ce composant, et le cycle qui en résulterait ne se voit qu'au build.
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

/**
 * Rendu de la page quand les statistiques détaillées ne peuvent pas être
 * calculées : course d'un chronométreur qui ne publie pas les splits de tous
 * les finishers, saisie manuelle, ou relais.
 *
 * Le message reste générique. Nommer le fournisseur ou afficher un jugement de
 * fiabilité n'apprendrait rien à un athlète et déplacerait la faute sur un tiers.
 */
export function UnavailableState({ athleteId }: { athleteId: number }) {
  return (
    <Card style={{ textAlign: "center", maxWidth: 620, margin: "48px auto" }}>
      <Eyebrow tone="muted">Comparaison détaillée</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--tcn-font-display)",
          fontSize: "clamp(24px, 4vw, 34px)",
          color: "var(--tcn-ink)",
          lineHeight: 1.1,
          margin: "10px 0 14px",
        }}
      >
        Statistiques indisponibles
      </h1>
      <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--tcn-text-secondary)" }}>
        Les statistiques détaillées ne s&apos;affichent que lorsque
        l&apos;intégralité des résultats du chronométreur a pu être récupérée
        pour cette épreuve.
      </p>
      <Link
        href={`/athletes/${athleteId}`}
        style={{
          display: "inline-block",
          marginTop: 22,
          fontFamily: "var(--tcn-font-cond)",
          fontWeight: 700,
          letterSpacing: "0.04em",
          color: "var(--tcn-orange)",
        }}
      >
        ← Retour aux résultats de l&apos;athlète
      </Link>
    </Card>
  );
}

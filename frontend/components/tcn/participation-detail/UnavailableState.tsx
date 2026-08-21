// Imports directs plutôt que via le barrel `@/components/tcn` : celui-ci
// réexporte ce composant, et le cycle qui en résulterait ne se voit qu'au build.
import { Card } from "../Card";
import { Eyebrow } from "../Eyebrow";

/**
 * Rendu, à la place des trois blocs calculés (comparaison, évolution,
 * matrice), quand les statistiques détaillées ne peuvent pas être calculées :
 * course d'un chronométreur qui ne publie pas les splits de tous les
 * finishers, saisie manuelle, ou relais. Le résultat de l'athlète lui-même
 * (`ResultRow`) reste rendu au-dessus — un geste ne doit jamais retirer de
 * l'information déjà à l'écran (#462, RES-1).
 *
 * Le message reste générique. Nommer le fournisseur ou afficher un jugement de
 * fiabilité n'apprendrait rien à un athlète et déplacerait la faute sur un tiers.
 *
 * Même largeur que les blocs qu'elle remplace, plutôt que centrée en pleine
 * page : ce n'est plus l'état unique de l'écran.
 */
export function UnavailableState() {
  return (
    <Card style={{ textAlign: "center", marginBottom: 24 }}>
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
        Comparaison au classement indisponible
      </h1>
      <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--tcn-text-secondary)" }}>
        Les statistiques détaillées ne s&apos;affichent que lorsque
        l&apos;intégralité des résultats du chronométreur a pu être récupérée
        pour cette épreuve.
      </p>
    </Card>
  );
}

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
 * Seul le relais a son message : ses statistiques sont exclues par choix (une
 * lecture individuelle d'un relais serait fausse), pas faute de données (#1091).
 *
 * Même largeur que les blocs qu'elle remplace, plutôt que centrée en pleine
 * page : ce n'est plus l'état unique de l'écran.
 */
export function UnavailableState({ isRelay }: { isRelay: boolean }) {
  return (
    <Card style={{ textAlign: "center", marginBottom: 24 }}>
      <Eyebrow tone="muted">Comparaison détaillée</Eyebrow>
      <h2
        style={{
          fontFamily: "var(--tcn-font-display)",
          fontSize: "clamp(24px, 4vw, 34px)",
          color: "var(--tcn-ink)",
          lineHeight: 1.1,
          margin: "10px 0 14px",
        }}
      >
        Comparaison au classement indisponible
      </h2>
      <p style={{ fontSize: 15, lineHeight: 1.6, color: "var(--tcn-text-secondary)" }}>
        {isRelay ? (
          <>
            Les statistiques individuelles ne sont pas calculées pour une
            épreuve en relais : le temps d&apos;une équipe ne se compare pas à
            celui d&apos;un athlète.
          </>
        ) : (
          <>
            Les statistiques détaillées ne s&apos;affichent que lorsque
            l&apos;intégralité des résultats du chronométreur a pu être récupérée
            pour cette épreuve.
          </>
        )}
      </p>
    </Card>
  );
}

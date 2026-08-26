/**
 * Signale que la ligne/fiche est celle de l'athlète retenu (#503, #504).
 *
 * Le chip, pas le fond qui l'accompagne, est le signifiant : la couleur seule
 * échouerait WCAG 1.4.1.
 */
export function VousChip() {
  return (
    <span
      style={{
        flex: "none",
        padding: "1px 7px",
        borderRadius: "var(--tcn-radius-sm)",
        background: "var(--tcn-orange-deep)",
        color: "#fff",
        fontFamily: "var(--tcn-font-cond)",
        fontWeight: 700,
        fontSize: 11,
        letterSpacing: ".04em",
      }}
    >
      Vous
    </span>
  );
}

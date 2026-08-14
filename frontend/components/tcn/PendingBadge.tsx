/** Mention explicite d'un résultat saisi manuellement, non encore vérifié
 *  par un bénévole (#270). Seule surface où une participation pendante est
 *  visible (FR-019) : distincte au premier coup d'œil, sans survol ni clic
 *  (SC-003). */
export function PendingBadge() {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 10px",
        borderRadius: 999,
        fontWeight: 700,
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: ".03em",
        background: "var(--tcn-warning-bg)",
        color: "var(--tcn-warning-text)",
        border: "1px solid var(--tcn-warning-border)",
      }}
    >
      En attente de validation
    </span>
  );
}

/** Mention explicite d'un résultat saisi manuellement, non encore vérifié
 *  par un bénévole (#270), ou signalé non conforme par un bénévole (#437).
 *  Seule surface où une participation pendante est visible (FR-019) :
 *  distincte au premier coup d'œil, sans survol ni clic (SC-003). */
export function PendingBadge({ rejected = false }: { rejected?: boolean }) {
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
        background: rejected ? "var(--tcn-danger-bg)" : "var(--tcn-warning-bg)",
        color: rejected ? "var(--tcn-danger-text)" : "var(--tcn-warning-text)",
        border: `1px solid ${rejected ? "var(--tcn-danger-border)" : "var(--tcn-warning-border)"}`,
      }}
    >
      {rejected ? "Non conforme" : "En attente de validation"}
    </span>
  );
}

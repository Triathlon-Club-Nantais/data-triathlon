import type { CSSProperties, ReactNode } from "react";

/** Bannière de statut inline (succès / avertissement / erreur). */
export function Alert({
  status = "success",
  title,
  children,
  action = null,
  style,
}: {
  status?: "success" | "warning" | "error";
  title?: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  style?: CSSProperties;
}) {
  // `sur` = la couleur du glyphe sur sa pastille, choisie par mesure et non par
  // convention : le glyphe faisait 12px en blanc dans les trois cas, soit 1,98:1
  // sur `--tcn-warning` #e6b020 et 7,61:1 sur `--tcn-danger` #992f00 (#299, #499).
  // L'encre y donne 8,42 et 2,19 ; sur `--tcn-success` #1f8a4d elle ferait
  // 3,82 contre 4,37 au blanc, qui reste donc le meilleur des deux là — atteindre
  // 4,5:1 sur le vert demanderait de bouger la couleur sémantique, hors périmètre.
  // `--tcn-danger` a foncé avec #499 (AA sur son propre aplat) : l'encre, qui
  // tenait sur l'ancien orange, tombe à 2,19:1 sur ce rouge plus sombre — c'est
  // désormais le blanc qui porte le glyphe.
  const palettes = {
    success: { bg: "var(--tcn-success-bg)", border: "var(--tcn-success-border)", icon: "var(--tcn-success)", sur: "#fff", title: "var(--tcn-success-text)", body: "var(--tcn-success-text2)", glyph: "✓" },
    warning: { bg: "var(--tcn-warning-bg)", border: "var(--tcn-warning-border)", icon: "var(--tcn-warning)", sur: "var(--tcn-ink)", title: "var(--tcn-warning-text)", body: "var(--tcn-warning-text2)", glyph: "!" },
    error: { bg: "var(--tcn-danger-bg)", border: "var(--tcn-danger-border)", icon: "var(--tcn-danger)", sur: "#fff", title: "var(--tcn-danger-text)", body: "var(--tcn-danger-text2)", glyph: "!" },
  } as const;
  const p = palettes[status];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: action ? "space-between" : "flex-start",
        // Sans quoi un titre long et une action se partagent ~290 px à 360 px,
        // et le titre tombe sur quatre lignes contre un bouton comprimé.
        flexWrap: "wrap",
        gap: 16,
        padding: "14px 18px",
        background: p.bg,
        border: `1.5px solid ${p.border}`,
        borderRadius: "var(--tcn-radius-xl)",
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        <div
          style={{
            flex: "none",
            width: 22,
            height: 22,
            borderRadius: 999,
            background: p.icon,
            color: p.sur,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 800,
            fontSize: 12,
            marginTop: 1,
          }}
        >
          {p.glyph}
        </div>
        <div>
          <div style={{ fontWeight: 800, color: p.title, fontSize: 14 }}>{title}</div>
          {children ? <div style={{ fontSize: 13, color: p.body, marginTop: 3, lineHeight: 1.5 }}>{children}</div> : null}
        </div>
      </div>
      {action}
    </div>
  );
}

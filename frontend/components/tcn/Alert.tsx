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
  const palettes = {
    success: { bg: "var(--tcn-success-bg)", border: "var(--tcn-success-border)", icon: "var(--tcn-success)", title: "var(--tcn-success-text)", body: "var(--tcn-success-text2)", glyph: "✓" },
    warning: { bg: "var(--tcn-warning-bg)", border: "var(--tcn-warning-border)", icon: "var(--tcn-warning)", title: "var(--tcn-warning-text)", body: "var(--tcn-warning-text2)", glyph: "!" },
    error: { bg: "var(--tcn-danger-bg)", border: "var(--tcn-danger-border)", icon: "var(--tcn-danger)", title: "var(--tcn-danger-text)", body: "var(--tcn-danger-text2)", glyph: "!" },
  } as const;
  const p = palettes[status];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: action ? "space-between" : "flex-start",
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
            color: "#fff",
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

import type { CSSProperties, ReactNode } from "react";

/** Chip clé/valeur des sous-en-têtes de page (« Format M », « Date … »). */
export function MetaPill({
  label,
  children,
  accent = false,
  dot = false,
  style,
}: {
  label?: ReactNode;
  children?: ReactNode;
  accent?: boolean;
  dot?: boolean;
  style?: CSSProperties;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "6px 13px",
        background: accent ? "var(--tcn-orange-08)" : "var(--tcn-surface)",
        border: accent ? "1px solid rgba(233,83,14,.25)" : "1px solid var(--tcn-border)",
        borderRadius: "var(--tcn-radius-pill)",
        fontSize: 13,
        fontWeight: accent ? 700 : 600,
        color: accent ? "var(--tcn-orange)" : "var(--tcn-text-body)",
        ...style,
      }}
    >
      {dot ? (
        <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 999, background: "var(--tcn-orange)" }} />
      ) : null}
      {label ? <span style={{ color: "var(--tcn-text-faint)" }}>{label}</span> : null}
      {children}
    </span>
  );
}

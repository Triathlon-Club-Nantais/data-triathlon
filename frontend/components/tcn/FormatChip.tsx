import type { CSSProperties, ReactNode } from "react";

/** Jeton de format de course (XS / S / M / L, ou une distance). */
export function FormatChip({
  children,
  style,
}: {
  children?: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        justifyContent: "center",
        alignItems: "center",
        minWidth: 26,
        padding: "3px 8px",
        background: "var(--tcn-fill)",
        borderRadius: "var(--tcn-radius-sm)",
        fontFamily: "var(--tcn-font-body)",
        fontWeight: 700,
        fontSize: 12,
        color: "var(--tcn-text-body)",
        ...style,
      }}
    >
      {children}
    </span>
  );
}

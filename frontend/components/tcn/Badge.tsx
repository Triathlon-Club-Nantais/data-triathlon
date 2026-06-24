import type { CSSProperties, ReactNode } from "react";

/** Pastille de statut/label TCN. `count` = chip numérique rond. */
export function Badge({
  variant = "neutral",
  count = false,
  dot = false,
  children,
  style,
}: {
  variant?: "neutral" | "orange" | "ink";
  count?: boolean;
  dot?: boolean;
  children?: ReactNode;
  style?: CSSProperties;
}) {
  if (count) {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          minWidth: 22,
          height: 22,
          padding: "0 6px",
          borderRadius: 999,
          background: "var(--tcn-orange-12)",
          color: "var(--tcn-orange)",
          fontWeight: 800,
          fontSize: 12,
          ...style,
        }}
      >
        {children}
      </span>
    );
  }

  const variants: Record<string, CSSProperties> = {
    neutral: { background: "rgba(28,30,34,.06)", color: "var(--tcn-ink)" },
    orange: { background: "var(--tcn-orange-12)", color: "var(--tcn-orange)" },
    ink: { background: "var(--tcn-ink)", color: "#fff" },
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "4px 11px",
        borderRadius: 999,
        fontWeight: 700,
        fontSize: 12,
        ...variants[variant],
        ...style,
      }}
    >
      {dot ? <span style={{ width: 7, height: 7, borderRadius: 999, background: "currentColor" }} /> : null}
      {children}
    </span>
  );
}

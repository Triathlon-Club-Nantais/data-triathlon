import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";

/** Bouton-icône circulaire (aide, fermeture, options). */
export function IconButton({
  variant = "outline",
  size = 42,
  children,
  style,
  ...rest
}: {
  variant?: "outline" | "soft" | "close";
  size?: number;
  children?: ReactNode;
  style?: CSSProperties;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "style">) {
  const variants: Record<string, CSSProperties> = {
    outline: { background: "var(--tcn-surface)", border: "1.5px solid var(--tcn-border-strong)", color: "var(--tcn-text-muted)" },
    soft: { background: "var(--tcn-fill)", border: "1.5px solid var(--tcn-border-strong)", color: "var(--tcn-text-faint)" },
    close: { background: "var(--tcn-fill)", border: "1px solid var(--tcn-border)", color: "var(--tcn-text-body)", borderRadius: "var(--tcn-radius-lg)" },
  };

  const isClose = variant === "close";
  return (
    <button
      type="button"
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: isClose ? 34 : size,
        height: isClose ? 34 : size,
        borderRadius: isClose ? "var(--tcn-radius-lg)" : "var(--tcn-radius-pill)",
        fontFamily: "var(--tcn-font-body)",
        fontWeight: 800,
        fontSize: 18,
        lineHeight: 1,
        cursor: "pointer",
        transition: "border-color var(--tcn-dur-fast), color var(--tcn-dur-fast), background var(--tcn-dur-fast)",
        ...variants[variant],
        ...style,
      }}
      {...rest}
    >
      {children}
    </button>
  );
}

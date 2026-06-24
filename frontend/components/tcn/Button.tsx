import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";

type ButtonProps = {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
  iconRight?: ReactNode;
  children?: ReactNode;
  style?: CSSProperties;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "style">;

/** Bouton d'action TCN — orange avec ombre orange signature. */
export function Button({
  variant = "primary",
  size = "md",
  icon = null,
  iconRight = null,
  children,
  style,
  ...rest
}: ButtonProps) {
  const sizes: Record<string, CSSProperties> = {
    sm: { padding: "9px 16px", fontSize: 13 },
    md: { padding: "12px 20px", fontSize: 14 },
    lg: { padding: "15px 26px", fontSize: 15 },
  };

  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    border: "none",
    borderRadius: "var(--tcn-radius-lg)",
    fontFamily: "var(--tcn-font-body)",
    fontWeight: variant === "primary" ? 800 : 700,
    lineHeight: 1,
    cursor: "pointer",
    textDecoration: "none",
    whiteSpace: "nowrap",
    transition: "background var(--tcn-dur-fast), color var(--tcn-dur-fast), border-color var(--tcn-dur-fast)",
    ...sizes[size],
  };

  const variants: Record<string, CSSProperties> = {
    primary: { background: "var(--tcn-orange)", color: "#fff", boxShadow: "var(--tcn-shadow-orange)" },
    secondary: { background: "var(--tcn-surface)", color: "var(--tcn-ink)", border: "1.5px solid var(--tcn-ink)" },
    ghost: { background: "var(--tcn-fill)", color: "var(--tcn-text-body)", border: "1px solid var(--tcn-border-strong)", fontWeight: 700 },
  };

  return (
    <button type="button" style={{ ...base, ...variants[variant], ...style }} {...rest}>
      {icon}
      {children}
      {iconRight}
    </button>
  );
}

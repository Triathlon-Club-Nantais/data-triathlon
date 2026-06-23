import type { CSSProperties, HTMLAttributes, ReactNode } from "react";

/** Surface de base TCN. `hero` = dégradé orange avec orbe décoratif. */
export function Card({
  variant = "default",
  padding = 28,
  children,
  style,
  ...rest
}: {
  variant?: "default" | "dashed" | "ink" | "hero";
  padding?: number | string;
  children?: ReactNode;
  style?: CSSProperties;
} & Omit<HTMLAttributes<HTMLDivElement>, "style">) {
  if (variant === "hero") {
    return (
      <div
        style={{
          position: "relative",
          overflow: "hidden",
          padding,
          background: "var(--tcn-orange-grad)",
          borderRadius: "var(--tcn-radius-3xl)",
          boxShadow: "var(--tcn-shadow-orange-xl)",
          color: "#fff",
          ...style,
        }}
        {...rest}
      >
        <div
          style={{
            position: "absolute",
            right: -30,
            bottom: -30,
            width: 140,
            height: 140,
            borderRadius: 999,
            background: "rgba(255,255,255,.12)",
          }}
        />
        {children}
      </div>
    );
  }

  const variants: Record<string, CSSProperties> = {
    default: { background: "var(--tcn-surface)", border: "1px solid var(--tcn-border)" },
    dashed: { background: "var(--tcn-surface)", border: "1px dashed var(--tcn-border-input)" },
    ink: { background: "var(--tcn-ink)", border: "none", color: "#fff" },
  };

  return (
    <div
      style={{
        padding,
        borderRadius: "var(--tcn-radius-3xl)",
        ...variants[variant],
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

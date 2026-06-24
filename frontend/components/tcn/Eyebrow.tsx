import type { CSSProperties, HTMLAttributes, ReactNode } from "react";

/** Overline TCN : capitales orange espacées au-dessus des titres. */
export function Eyebrow({
  tone = "orange",
  children,
  style,
  ...rest
}: {
  tone?: "orange" | "muted";
  children?: ReactNode;
  style?: CSSProperties;
} & Omit<HTMLAttributes<HTMLDivElement>, "style">) {
  const colors = { orange: "var(--tcn-orange)", muted: "var(--tcn-text-faint)" } as const;
  return (
    <div
      style={{
        fontFamily: "var(--tcn-font-cond)",
        fontWeight: 700,
        fontSize: 13,
        letterSpacing: "0.16em",
        textTransform: "uppercase",
        color: colors[tone],
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}

import type { CSSProperties, ReactNode } from "react";

/** Tuile KPI TCN. `hero` utilise le dégradé orange. */
export function StatCard({
  label,
  value,
  icon = null,
  accent = true,
  valueColor = "var(--tcn-ink)",
  delta = null,
  variant = "default",
  style,
}: {
  label?: ReactNode;
  value?: ReactNode;
  icon?: ReactNode;
  accent?: boolean;
  valueColor?: string;
  delta?: ReactNode;
  variant?: "default" | "hero";
  style?: CSSProperties;
}) {
  if (variant === "hero") {
    return (
      <div
        style={{
          position: "relative",
          overflow: "hidden",
          padding: "28px 26px",
          background: "var(--tcn-orange-grad)",
          borderRadius: "var(--tcn-radius-3xl)",
          boxShadow: "var(--tcn-shadow-orange-xl)",
          ...style,
        }}
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
        <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: ".04em", textTransform: "uppercase", color: "rgba(255,255,255,.85)" }}>
          {label}
        </div>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 86, lineHeight: 0.95, color: "#fff", margin: "10px 0 8px", whiteSpace: "nowrap" }}>
          {value}
        </div>
        {delta ? (
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 12px", background: "rgba(255,255,255,.2)", color: "#fff", borderRadius: 999, fontSize: 13, fontWeight: 800 }}>
            {delta}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div style={{ padding: "26px 24px", background: "var(--tcn-surface)", border: "1px solid var(--tcn-border)", borderRadius: "var(--tcn-radius-3xl)", ...style }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--tcn-text-muted)" }}>
          {label}
        </div>
        {icon ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 34, height: 34, borderRadius: "var(--tcn-radius-lg)", background: "var(--tcn-orange-10)" }}>
            {icon}
          </div>
        ) : null}
      </div>
      <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 68, lineHeight: 1, color: valueColor, marginTop: 10 }}>
        {value}
      </div>
      {accent ? (
        <div style={{ height: 4, width: 48, background: "var(--tcn-orange)", borderRadius: 999, marginTop: 8 }} />
      ) : null}
    </div>
  );
}

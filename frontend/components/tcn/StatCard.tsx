import type { CSSProperties, ReactNode } from "react";

/** Tuile KPI TCN. `hero` utilise le dégradé orange ; `hint` ajoute une sous-ligne, variant `default` uniquement (silencieusement ignoré en `hero`). */
export function StatCard({
  label,
  value,
  icon = null,
  accent = true,
  valueColor = "var(--tcn-ink)",
  delta = null,
  hint = null,
  variant = "default",
  style,
}: {
  label?: ReactNode;
  value?: ReactNode;
  icon?: ReactNode;
  accent?: boolean;
  valueColor?: string;
  delta?: ReactNode;
  hint?: ReactNode;
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
        {/* Encre sur le dégradé (#299) : du blanc n'y tenait que 3,68:1 à
            l'extrémité #E9530E, et la hiérarchie ne se portait plus qu'à
            l'opacité — 85 % de blanc pour le libellé. Elle passe à la taille et
            aux capitales, les trois textes étant désormais en encre pleine :
            4,54:1 au pire pour le libellé et la valeur, 5,73:1 pour la pastille,
            dont le blanc à 20 % éclaircit le fond au lieu de l'assombrir. */}
        <div style={{ fontWeight: 700, fontSize: 13, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--tcn-ink)" }}>
          {label}
        </div>
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 86, lineHeight: 0.95, color: "var(--tcn-ink)", margin: "10px 0 8px", whiteSpace: "nowrap" }}>
          {value}
        </div>
        {delta ? (
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 12px", background: "rgba(255,255,255,.2)", color: "var(--tcn-ink)", borderRadius: 999, fontSize: 13, fontWeight: 800 }}>
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
      {delta ? (
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--tcn-text-faint)", marginTop: 10 }}>
          {delta}
        </div>
      ) : null}
      {hint ? (
        <div data-testid="statcard-hint" style={{ marginTop: 8, fontSize: 13, fontWeight: 600, color: "var(--tcn-text-faint)" }}>
          {hint}
        </div>
      ) : null}
    </div>
  );
}

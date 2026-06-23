import type { CSSProperties, ReactNode } from "react";

/** Pastille de classement (Anton). Teinte automatique selon la place. */
export function PlaceBadge({
  place,
  tier,
  style,
}: {
  place?: ReactNode;
  tier?: "podium" | "top" | "rest";
  style?: CSSProperties;
}) {
  const n = typeof place === "number" ? place : parseInt(String(place ?? ""), 10);
  const resolved = tier || (n <= 3 ? "podium" : n <= 10 ? "top" : "rest");

  const tiers: Record<string, CSSProperties> = {
    podium: { background: "var(--tcn-orange-12)", color: "var(--tcn-orange)" },
    top: { background: "rgba(28,30,34,.06)", color: "var(--tcn-ink)" },
    rest: { background: "transparent", color: "var(--tcn-text-muted)" },
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: 34,
        padding: "4px 9px",
        borderRadius: "var(--tcn-radius-md)",
        fontFamily: "var(--tcn-font-display)",
        fontSize: 16,
        ...tiers[resolved],
        ...style,
      }}
    >
      {place}
    </span>
  );
}

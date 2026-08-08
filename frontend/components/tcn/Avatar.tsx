import type { CSSProperties } from "react";

/** Avatar TCN : initiales sur dégradé orange. */
export function Avatar({
  name = "",
  initials,
  size = 40,
  style,
}: {
  name?: string;
  initials?: string;
  size?: number;
  style?: CSSProperties;
}) {
  let derived = initials;
  if (!derived && name) {
    const parts = name.trim().split(/\s+/);
    derived = ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
  }
  const large = size >= 64;
  return (
    // `aria-hidden` : l'avatar est décoratif partout où il sert, le nom est
    // toujours en clair juste à côté. Sans lui, un lecteur d'écran annonce
    // « M D Marie Dupont ». Hérité d'`ui/initials-avatar`, qu'il remplace.
    <div
      aria-hidden
      style={{
        flex: "none",
        width: size,
        height: size,
        borderRadius: "var(--tcn-radius-pill)",
        background: "var(--tcn-orange-grad)",
        color: "#fff",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: large ? "var(--tcn-font-display)" : "var(--tcn-font-body)",
        fontWeight: large ? 400 : 800,
        fontSize: large ? Math.round(size * 0.39) : Math.round(size * 0.35),
        boxShadow: large ? "var(--tcn-shadow-orange-lg)" : "none",
        ...style,
      }}
    >
      {derived}
    </div>
  );
}

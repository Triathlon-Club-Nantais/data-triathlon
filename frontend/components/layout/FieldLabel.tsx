import type { ReactNode } from "react";

/** Petit libellé visuel au-dessus d'un contrôle de filtrage (NAV-5, #483). */
export function FieldLabel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 12,
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: ".04em",
        color: "var(--tcn-text-faint)",
        marginBottom: 6,
      }}
    >
      {children}
    </div>
  );
}

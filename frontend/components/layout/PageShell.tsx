import type { ReactNode } from "react";

/** Conteneur de page TCN : largeur max + gouttières (le layout est full-width). */
export function PageShell({ form = false, children }: { form?: boolean; children: ReactNode }) {
  return (
    <div
      style={{
        maxWidth: form ? "var(--tcn-content-form)" : "var(--tcn-content-max)",
        margin: "0 auto",
        padding: "36px 40px 64px",
      }}
    >
      {children}
    </div>
  );
}

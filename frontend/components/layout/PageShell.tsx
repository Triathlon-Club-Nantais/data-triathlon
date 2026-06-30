import type { ReactNode } from "react";

/** Conteneur de page TCN : largeur max + gouttières (le layout est full-width). */
export function PageShell({ form = false, children }: { form?: boolean; children: ReactNode }) {
  return (
    <div
      className="mx-auto px-4 pt-6 pb-16 sm:px-8 sm:pt-9 md:px-10"
      style={{
        maxWidth: form ? "var(--tcn-content-form)" : "var(--tcn-content-max)",
      }}
    >
      {children}
    </div>
  );
}

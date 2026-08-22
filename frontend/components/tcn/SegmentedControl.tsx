import type { CSSProperties, ReactNode } from "react";

type Option = string | { value: string; label: ReactNode; dot?: boolean };

/**
 * Toggle choix-unique. Segment actif = encre ; variante orange pour les formats.
 *
 * Chaque bouton porte `aria-pressed` (état déjà calculé ici, pas un prop
 * séparé) et la classe `tcn-segmented-btn` (`app/globals.css`), seule à poser
 * un `:focus-visible` à 3:1 — en style inline pur, ce composant n'a aucun
 * autre moyen de l'exprimer (#342). Le conteneur ne porte pas de rôle : c'est
 * à l'appelant de choisir `role="group"` (bouton-groupe, précédent :
 * `ScopeToggle`) selon son contexte.
 */
export function SegmentedControl({
  options = [],
  value,
  onChange = () => {},
  tone = "ink",
  style,
}: {
  options?: Option[];
  value?: string;
  onChange?: (value: string) => void;
  tone?: "ink" | "orange";
  style?: CSSProperties;
}) {
  return (
    <div style={{ display: "flex", gap: 8, ...style }}>
      {options.map((opt) => {
        const val = typeof opt === "string" ? opt : opt.value;
        const label = typeof opt === "string" ? opt : opt.label;
        const dot = typeof opt === "object" ? opt.dot : false;
        const active = val === value;

        const inkStyle: CSSProperties = active
          ? { background: "var(--tcn-ink)", color: "#fff", border: "1.5px solid var(--tcn-ink)" }
          : { background: "var(--tcn-surface)", color: "var(--tcn-text-body)", border: "1.5px solid var(--tcn-border-input)" };

        const orangeStyle: CSSProperties = active
          ? { background: "var(--tcn-orange-10)", color: "var(--tcn-orange-deeper)", border: "1.5px solid var(--tcn-orange)" }
          : { background: "var(--tcn-fill)", color: "var(--tcn-text-body)", border: "1.5px solid var(--tcn-border)" };

        const skin = tone === "orange" ? orangeStyle : inkStyle;

        return (
          <button
            key={val}
            type="button"
            className="tcn-segmented-btn"
            aria-pressed={active}
            onClick={() => onChange(val)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              flex: tone === "orange" ? 1 : "none",
              padding: tone === "orange" ? "10px 0" : "9px 16px",
              // Plancher tactile WCAG 2.2 2.5.8 (#479) : un des trois
              // contrôles de la barre d'outils du dashboard mesurés entre
              // 26 et 34 px par l'audit UI/UX.
              minHeight: 28,
              borderRadius: "var(--tcn-radius-lg)",
              fontFamily: tone === "orange" ? "var(--tcn-font-display)" : "var(--tcn-font-body)",
              fontSize: tone === "orange" ? 17 : 13,
              fontWeight: tone === "orange" ? 400 : 700,
              cursor: "pointer",
              transition: "all var(--tcn-dur-fast)",
              ...skin,
            }}
          >
            {dot ? <span style={{ width: 8, height: 8, borderRadius: 999, background: "var(--tcn-orange)" }} /> : null}
            {label}
          </button>
        );
      })}
    </div>
  );
}

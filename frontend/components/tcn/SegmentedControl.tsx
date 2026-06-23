import type { CSSProperties, ReactNode } from "react";

type Option = string | { value: string; label: ReactNode; dot?: boolean };

/** Toggle choix-unique. Segment actif = encre ; variante orange pour les formats. */
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
          ? { background: "var(--tcn-orange-10)", color: "var(--tcn-orange)", border: "1.5px solid var(--tcn-orange)" }
          : { background: "var(--tcn-fill)", color: "var(--tcn-text-body)", border: "1.5px solid var(--tcn-border)" };

        const skin = tone === "orange" ? orangeStyle : inkStyle;

        return (
          <button
            key={val}
            onClick={() => onChange(val)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              flex: tone === "orange" ? 1 : "none",
              padding: tone === "orange" ? "10px 0" : "9px 16px",
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

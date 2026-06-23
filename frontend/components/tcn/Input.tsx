import type { CSSProperties, InputHTMLAttributes, ReactNode } from "react";

/** Champ texte TCN sur fill chaud, avec icône optionnelle et bordure de statut. */
export function Input({
  icon = null,
  status = "default",
  style,
  containerStyle,
  ...rest
}: {
  icon?: ReactNode;
  status?: "default" | "error" | "warning" | "active";
  style?: CSSProperties;
  containerStyle?: CSSProperties;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "style">) {
  const statusBorders: Record<string, string> = {
    default: "var(--tcn-border)",
    error: "var(--tcn-danger-border)",
    warning: "var(--tcn-warning-border)",
    active: "var(--tcn-orange)",
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "13px 16px",
        background: "var(--tcn-fill)",
        border: `1.5px solid ${statusBorders[status]}`,
        borderRadius: "var(--tcn-radius-xl)",
        transition: "border-color var(--tcn-dur-fast)",
        ...containerStyle,
      }}
    >
      {icon ? <span style={{ color: "var(--tcn-text-faint)", fontSize: 15, display: "inline-flex" }}>{icon}</span> : null}
      <input
        style={{
          flex: 1,
          width: "100%",
          background: "transparent",
          border: "none",
          outline: "none",
          color: "var(--tcn-text)",
          fontFamily: "var(--tcn-font-body)",
          fontSize: 15,
          ...style,
        }}
        {...rest}
      />
    </div>
  );
}

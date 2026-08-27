import type { CSSProperties, InputHTMLAttributes, ReactNode, Ref } from "react";

/** Champ texte TCN sur fill chaud, avec icône optionnelle et bordure de statut. */
export function Input({
  ref,
  icon = null,
  actions = null,
  status = "default",
  style,
  containerStyle,
  className,
  ...rest
}: {
  ref?: Ref<HTMLInputElement>;
  icon?: ReactNode;
  /** Contrôles posés **dans** le champ, à droite du texte (effacer, coller).
   *  Leur présence resserre le rembourrage vertical : une cible tactile de
   *  44px doit tenir dans la boîte sans la faire grandir de 26px. */
  actions?: ReactNode;
  status?: "default" | "error" | "warning" | "active";
  style?: CSSProperties;
  containerStyle?: CSSProperties;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "style">) {
  const statusBorders: Record<string, string> = {
    // `--tcn-border` ne vaut que 1,10:1 sur le `--tcn-fill` du champ — un
    // contour de composant illisible (WCAG 1.4.11, #652). `--tcn-text-faint`
    // est déjà le premier jeton de bordure à passer 3:1 sur ce même fond
    // (`ParticipationAdminActions`, #439).
    default: "var(--tcn-text-faint)",
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
        padding: actions ? "4px 6px 4px 16px" : "13px 16px",
        background: "var(--tcn-fill)",
        border: `1.5px solid ${statusBorders[status]}`,
        borderRadius: "var(--tcn-radius-xl)",
        transition: "border-color var(--tcn-dur-fast)",
        ...containerStyle,
      }}
    >
      {icon ? <span style={{ color: "var(--tcn-text-faint)", fontSize: 15, display: "inline-flex" }}>{icon}</span> : null}
      <input
        ref={ref}
        className={["tcn-input", className].filter(Boolean).join(" ")}
        style={{
          flex: 1,
          // Largeur minimale nulle : sans elle, la largeur intrinsèque d'un
          // `<input>` (~20 caractères) pousse les actions hors de la boîte.
          minWidth: 0,
          background: "transparent",
          border: "none",
          color: "var(--tcn-text)",
          fontFamily: "var(--tcn-font-body)",
          // La taille de police est dans `.tcn-input` : une valeur en ligne
          // rendrait la media query du seuil iOS inerte (#492, ACT-5).
          ...style,
        }}
        {...rest}
      />
      {actions}
    </div>
  );
}

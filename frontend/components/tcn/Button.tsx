import type { ButtonHTMLAttributes, CSSProperties, ReactNode, Ref } from "react";

type ButtonProps = {
  variant?: "primary" | "secondary" | "ghost" | "destructive";
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
  iconRight?: ReactNode;
  children?: ReactNode;
  style?: CSSProperties;
  /** Une prop comme une autre en React 19 : rendre le focus à ce bouton après un dialogue. */
  ref?: Ref<HTMLButtonElement>;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "style">;

/**
 * Bouton d'action TCN — orange avec ombre orange signature.
 *
 * Les styles vivent en classes dans `globals.css` (`.tcn-btn*`), pas en
 * `CSSProperties` en ligne : `:hover`, `:focus-visible` et `disabled` y sont
 * inexprimables, et c'était la cause commune de trois défauts d'accessibilité
 * (#299). `style` ne sert plus qu'aux ajustements d'appelant.
 */
export function Button({
  variant = "primary",
  size = "md",
  icon = null,
  iconRight = null,
  children,
  className,
  style,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      className={["tcn-btn", `tcn-btn--${size}`, `tcn-btn--${variant}`, className].filter(Boolean).join(" ")}
      style={style}
      {...rest}
    >
      {icon}
      {children}
      {iconRight}
    </button>
  );
}

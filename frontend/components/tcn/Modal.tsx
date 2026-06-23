"use client";
import type { CSSProperties, ReactNode } from "react";
import { IconButton } from "./IconButton";
import { Eyebrow } from "./Eyebrow";

/** Dialogue centré sur scrim encre flouté (eyebrow + titre Anton + fermeture). */
export function Modal({
  open = true,
  eyebrow,
  title,
  onClose = () => {},
  footer = null,
  width = 520,
  children,
  style,
}: {
  open?: boolean;
  eyebrow?: ReactNode;
  title?: ReactNode;
  onClose?: () => void;
  footer?: ReactNode;
  width?: number;
  children?: ReactNode;
  style?: CSSProperties;
}) {
  if (!open) return null;
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--tcn-overlay)",
        backdropFilter: "blur(3px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 50,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width,
          maxWidth: "calc(100vw - 32px)",
          maxHeight: "82vh",
          display: "flex",
          flexDirection: "column",
          background: "var(--tcn-surface)",
          borderRadius: "var(--tcn-radius-modal)",
          boxShadow: "var(--tcn-shadow-modal)",
          overflow: "hidden",
          ...style,
        }}
      >
        <div style={{ padding: "24px 28px 18px", borderBottom: "1px solid var(--tcn-border)", display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
          <div>
            {eyebrow ? <Eyebrow style={{ fontSize: 12 }}>{eyebrow}</Eyebrow> : null}
            <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 26, color: "var(--tcn-ink)", marginTop: eyebrow ? 4 : 0 }}>
              {title}
            </div>
          </div>
          <IconButton variant="close" onClick={onClose} aria-label="Fermer">×</IconButton>
        </div>

        <div style={{ overflowY: "auto", padding: "22px 28px 26px" }}>{children}</div>

        {footer ? <div style={{ padding: "16px 28px", borderTop: "1px solid var(--tcn-border)" }}>{footer}</div> : null}
      </div>
    </div>
  );
}

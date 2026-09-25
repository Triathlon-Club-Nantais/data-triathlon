"use client";
import { useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { IconButton } from "./IconButton";
import { Eyebrow } from "./Eyebrow";

/**
 * Dialogue centré sur scrim encre flouté (eyebrow + titre Anton + fermeture).
 *
 * Piège du focus, inertie du reste de la page et retour du focus confiés au
 * Dialog de Base UI (#988) : le piège maison ne tenait que sur ses bornes.
 */
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
  const titleId = useId();
  const popupRef = useRef<HTMLDivElement>(null);

  // Déclencheur lu au rendu : un enfant `autoFocus` prend le focus au commit et
  // passerait sinon pour le déclencheur (#955).
  const [declencheur, setDeclencheur] = useState<HTMLElement | null>(null);
  const [ouvertVu, setOuvertVu] = useState(false);
  if (open !== ouvertVu) {
    setOuvertVu(open);
    // Gardé à la fermeture : `finalFocus` le lit après le passage à `open=false`.
    if (open) {
      setDeclencheur(
        typeof document !== "undefined" && document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null,
      );
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(ouvert) => !ouvert && onClose()}>
      <Dialog.Portal>
        <Dialog.Backdrop
          style={{ position: "fixed", inset: 0, background: "var(--tcn-overlay)", backdropFilter: "blur(3px)", zIndex: 50 }}
        />
        <Dialog.Viewport
          style={{ position: "fixed", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50 }}
        >
          <Dialog.Popup
            ref={popupRef}
            // Base UI rend le reste de la page inerte sans poser cet attribut.
            aria-modal="true"
            aria-labelledby={title ? titleId : undefined}
            initialFocus={() => {
              const actif = document.activeElement;
              return actif instanceof HTMLElement && popupRef.current?.contains(actif) ? actif : true;
            }}
            finalFocus={() => (declencheur?.isConnected ? declencheur : true)}
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
              outline: "none",
              ...style,
            }}
          >
            <div style={{ padding: "24px 28px 18px", borderBottom: "1px solid var(--tcn-border)", display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16 }}>
              <div>
                {eyebrow ? <Eyebrow style={{ fontSize: 12 }}>{eyebrow}</Eyebrow> : null}
                <div id={titleId} style={{ fontFamily: "var(--tcn-font-display)", fontSize: 26, color: "var(--tcn-ink)", marginTop: eyebrow ? 4 : 0 }}>
                  {title}
                </div>
              </div>
              <IconButton variant="close" onClick={onClose} aria-label="Fermer">×</IconButton>
            </div>

            <div style={{ overflowY: "auto", padding: "22px 28px 26px" }}>{children}</div>

            {footer ? <div style={{ padding: "16px 28px", borderTop: "1px solid var(--tcn-border)" }}>{footer}</div> : null}
          </Dialog.Popup>
        </Dialog.Viewport>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

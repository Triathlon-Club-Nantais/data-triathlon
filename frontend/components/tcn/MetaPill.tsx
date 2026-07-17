import type { CSSProperties, ReactNode } from "react";

import { isHttpUrl } from "@/lib/utils/url";

/**
 * Chip clé/valeur des sous-en-têtes de page (« Format M », « Date … »).
 *
 * Avec `href`, le chip devient un lien vers un site tiers (la page de résultats
 * du chronométreur) : un `<a>` natif, pas un `Link` — Next ne préchargera jamais
 * une URL externe, et le lien doit fonctionner sans routeur. Le lien n'est rendu
 * que pour une URL `http(s)` ; sinon on retombe sur un simple chip.
 */
export function MetaPill({
  label,
  children,
  accent = false,
  dot = false,
  href,
  title,
  style,
}: {
  label?: ReactNode;
  children?: ReactNode;
  accent?: boolean;
  dot?: boolean;
  href?: string;
  title?: string;
  style?: CSSProperties;
}) {
  const isLink = isHttpUrl(href);
  const Tag = isLink ? "a" : "span";
  const linkProps = isLink
    ? { href, target: "_blank", rel: "noopener noreferrer", className: "hover:underline" }
    : {};
  return (
    <Tag
      {...linkProps}
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "6px 13px",
        background: accent ? "var(--tcn-orange-08)" : "var(--tcn-surface)",
        border: accent ? "1px solid rgba(233,83,14,.25)" : "1px solid var(--tcn-border)",
        borderRadius: "var(--tcn-radius-pill)",
        fontSize: 13,
        fontWeight: accent ? 700 : 600,
        color: accent ? "var(--tcn-orange)" : "var(--tcn-text-body)",
        ...style,
      }}
    >
      {dot ? (
        <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 999, background: "var(--tcn-orange)" }} />
      ) : null}
      {label ? <span style={{ color: "var(--tcn-text-faint)" }}>{label}</span> : null}
      {children}
    </Tag>
  );
}

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

/**
 * Une ligne de tableau repliée en carte, pour les largeurs où la grille ne
 * tient plus (#461, `RESP-1`).
 *
 * **Sans état, donc sans `"use client"`** : `/ajouter` est un Server Component
 * et doit le rester. Le dépliant est un `<details>` natif, pas un état React.
 *
 * **Le dépliant et les actions sont FRÈRES de la zone cliquable, jamais
 * enfants** : un `<a>` ou un `<button>` imbriqué dans un `<a>` est du HTML
 * invalide. C'est déjà la raison pour laquelle `EventsTable` sort « Voir la
 * preuve » de sa ligne ; la coquille ne fait que généraliser la contrainte.
 *
 * Le composant ne sait rien des colonnes : ce que les quatre tableaux partagent
 * est un dessin, pas une structure. Chaque écran verse son contenu.
 */
export function LigneCarte({
  href,
  onSelect,
  ariaLabel,
  ouvert,
  surtitre,
  marqueur,
  titre,
  valeur,
  meta,
  depliant,
  actions,
  accent = false,
  attenue = false,
}: {
  /** Cible de la zone cliquable, quand la carte navigue. Exclusif avec `onSelect`. */
  href?: string;
  /** Action de la zone cliquable, quand la carte ne navigue pas. */
  onSelect?: () => void;
  /** Nom accessible du bouton — un `<button>` n'a pas d'URL à annoncer. */
  ariaLabel?: string;
  /** `aria-expanded` du bouton, pour une carte qui en replie d'autres (#463). */
  ouvert?: boolean;
  /** Ligne au-dessus du titre : une date, en général. */
  surtitre?: ReactNode;
  /** Pastille à gauche du titre : `PlaceBadge`, `StatusBadge`. */
  marqueur?: ReactNode;
  titre: ReactNode;
  /** Valeur forte alignée à droite : temps total, compteur. */
  valeur?: ReactNode;
  /** Bande secondaire sous le titre. */
  meta?: ReactNode;
  depliant?: { libelle: string; contenu: ReactNode };
  /** Sous-ligne d'actions, rendue hors de la zone cliquable. */
  actions?: ReactNode;
  /** Liseré orange TCN, comme le `borderLeft` des lignes du classement. */
  accent?: boolean;
  /** Fond grisé des non-finishers. */
  attenue?: boolean;
}) {
  const contenu = (
    <>
      {surtitre ? <div style={STYLE_SURTITRE}>{surtitre}</div> : null}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
        {marqueur ? <div style={{ flex: "none" }}>{marqueur}</div> : null}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={STYLE_TITRE}>{titre}</div>
          {meta ? <div style={STYLE_META}>{meta}</div> : null}
        </div>
        {valeur ? <div style={STYLE_VALEUR}>{valeur}</div> : null}
      </div>
    </>
  );

  return (
    <article
      style={{
        borderBottom: "1px solid var(--tcn-border-faint)",
        // Toujours 3 px, transparents à défaut : un liseré qui n'existe que
        // sur les lignes du club décalerait toutes les autres de 3 px.
        borderLeft: `3px solid ${accent ? "var(--tcn-orange)" : "transparent"}`,
        background: attenue
          ? "color-mix(in srgb, var(--tcn-grey-400) 15%, transparent)"
          : undefined,
      }}
    >
      {href ? (
        <Link href={href} className="tcn-rowlink" style={STYLE_CLIC}>
          {contenu}
        </Link>
      ) : (
        <button
          type="button"
          onClick={onSelect}
          aria-label={ariaLabel}
          aria-expanded={ouvert}
          className="tcn-rowlink"
          style={{ ...STYLE_CLIC, width: "100%", textAlign: "left", border: "none" }}
        >
          {contenu}
        </button>
      )}
      {depliant ? (
        <details style={{ padding: "0 16px 8px" }}>
          <summary style={STYLE_RESUME}>{depliant.libelle}</summary>
          <div style={{ paddingBottom: 8 }}>{depliant.contenu}</div>
        </details>
      ) : null}
      {actions}
    </article>
  );
}

// `minHeight: 44` : plancher tactile WCAG 2.2 2.5.8, le même seuil que la
// coquille de navigation se donne déjà (AppNav).
const STYLE_CLIC = {
  display: "block",
  minHeight: 44,
  padding: "12px 16px",
} as const;

const STYLE_RESUME = {
  display: "flex",
  alignItems: "center",
  minHeight: 44,
  fontSize: 13,
  fontWeight: 700,
  color: "var(--tcn-text-muted)",
  cursor: "pointer",
} as const;

const STYLE_SURTITRE = {
  marginBottom: 4,
  fontSize: 13,
  fontWeight: 600,
  color: "var(--tcn-text-muted)",
} as const;

const STYLE_TITRE = {
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: 8,
  fontSize: 15,
  fontWeight: 700,
  color: "var(--tcn-ink)",
} as const satisfies CSSProperties;

const STYLE_META = {
  marginTop: 4,
  display: "flex",
  alignItems: "center",
  flexWrap: "wrap",
  gap: 8,
  fontSize: 13,
  color: "var(--tcn-text-body)",
} as const satisfies CSSProperties;

const STYLE_VALEUR = {
  flex: "none",
  fontFamily: "var(--tcn-font-cond)",
  fontWeight: 700,
  fontSize: 16,
  color: "var(--tcn-ink)",
  textAlign: "right",
} as const satisfies CSSProperties;

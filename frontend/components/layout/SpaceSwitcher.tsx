"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { libelleCompteur } from "@/lib/queries/nav-badges";
import { SPACES, type SpaceId } from "./nav.config";

export type SwitcherSpace = { id: SpaceId; label: string; href: string; count?: number };

/**
 * Mène d'un espace à l'autre par des liens à icône (#1336), tous visibles :
 * - `row` : panneau déplié et tiroir mobile, icône sur libellé (288 px ne
 *   tiennent pas trois libellés côte à côte) ;
 * - `column` : rail replié, icônes empilées avec infobulle.
 * Pas d'icône seule dans l'en-tête mobile : sans libellé ni survol au doigt,
 * elle s'y lisait comme une action (revue UI/UX de #1353).
 */
export function SpaceSwitcher({
  current,
  spaces,
  layout,
}: {
  current: SpaceId;
  spaces: SwitcherSpace[];
  layout: "row" | "column";
}) {
  if (spaces.length < 2) return null;
  const compact = layout === "column";

  return (
    <div
      role="group"
      aria-label="Espaces"
      style={{ flex: compact ? "none" : 1, display: "flex", flexDirection: compact ? "column" : "row", gap: 4 }}
    >
      {spaces.map((espace) => {
        const Icon = SPACES[espace.id].icon;
        const actif = espace.id === current;
        const annonce = espace.count ? libelleCompteur("backoffice", espace.count) : undefined;
        const nom = annonce ? `${espace.label}, ${annonce}` : espace.label;
        const lien = {
          href: espace.href,
          prefetch: false,
          "aria-current": actif ? ("true" as const) : undefined,
          "aria-label": nom,
          className: "tcn-space-tile",
          style: tuile(actif, compact),
        };
        const contenu = (
          <>
            <Icon size={18} aria-hidden />
            {!compact && <span>{espace.label}</span>}
            {espace.count ? (
              <span aria-hidden="true" style={pastille(compact)}>
                {espace.count}
              </span>
            ) : null}
          </>
        );
        return compact ? (
          <Tooltip key={espace.id}>
            <TooltipTrigger render={<Link {...lien} />}>{contenu}</TooltipTrigger>
            <TooltipContent>{nom}</TooltipContent>
          </Tooltip>
        ) : (
          <Link key={espace.id} {...lien}>
            {contenu}
          </Link>
        );
      })}
    </div>
  );
}

/**
 * L'espace courant se dit par sa bordure autant que par sa teinte (WCAG 1.4.1).
 * Son texte prend `-deeper` : `-deep` ne tient que 4,13:1 sur le fond teinté.
 * Le fond des autres tuiles n'est pas posé en ligne, sans quoi il battrait le
 * `:hover` de `.tcn-space-tile`.
 */
function tuile(actif: boolean, compact: boolean): CSSProperties {
  return {
    position: "relative",
    flex: compact ? "none" : 1,
    minWidth: 0,
    width: compact ? 44 : undefined,
    height: compact ? 44 : 52,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
    borderRadius: "var(--tcn-radius-lg)",
    border: `1.5px solid ${actif ? "var(--tcn-orange-deep)" : "transparent"}`,
    ...(actif ? { background: "var(--tcn-orange-08)", color: "var(--tcn-orange-deeper)" } : { color: "var(--tcn-text-muted)" }),
    textDecoration: "none",
    whiteSpace: "nowrap",
    fontFamily: "var(--tcn-font-cond)",
    fontWeight: 700,
    fontSize: 11,
  };
}

function pastille(compact: boolean): CSSProperties {
  return {
    position: "absolute",
    top: compact ? 2 : 4,
    ...(compact ? { right: 0 } : { left: "calc(50% + 6px)" }),
    minWidth: 16,
    padding: "0 4px",
    borderRadius: "var(--tcn-radius-pill)",
    background: "var(--tcn-orange-deep)",
    color: "#fff",
    fontSize: 11,
    fontWeight: 700,
    lineHeight: "16px",
    textAlign: "center",
  };
}

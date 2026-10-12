"use client";

import Link from "next/link";
import type { CSSProperties } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { libelleCompteur } from "@/lib/queries/nav-badges";
import { SPACES, type SpaceId } from "./nav.config";

export type SwitcherSpace = { id: SpaceId; label: string; href: string; count?: number };

/**
 * Mène d'un espace à l'autre par des liens à icône (#1336), tous visibles :
 * - `row` : panneau déplié, icône sur libellé (288 px ne tiennent pas trois
 *   libellés côte à côte) ;
 * - `column` : rail replié, icônes empilées avec infobulle ;
 * - `header` : barre mobile, les **autres** espaces seuls, faute de largeur ;
 *   l'espace courant s'y lit déjà dans la barre basse.
 */
export function SpaceSwitcher({
  current,
  spaces,
  layout,
}: {
  current: SpaceId;
  spaces: SwitcherSpace[];
  layout: "row" | "column" | "header";
}) {
  if (spaces.length < 2) return null;
  const compact = layout !== "row";
  const affiches = layout === "header" ? spaces.filter((e) => e.id !== current) : spaces;

  return (
    <div
      role="group"
      aria-label={layout === "header" ? "Autres espaces" : "Espaces"}
      style={{ flex: layout === "row" ? 1 : "none", display: "flex", flexDirection: layout === "column" ? "column" : "row", gap: 4 }}
    >
      {affiches.map((espace) => {
        const Icon = SPACES[espace.id].icon;
        const actif = espace.id === current;
        const annonce = espace.count ? libelleCompteur("backoffice", espace.count) : undefined;
        const nom = annonce ? `${espace.label}, ${annonce}` : espace.label;
        const lien = {
          href: espace.href,
          prefetch: false,
          "aria-current": actif ? ("true" as const) : undefined,
          "aria-label": nom,
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

/** L'espace courant se dit par sa bordure autant que par sa teinte (WCAG 1.4.1). */
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
    background: actif ? "var(--tcn-orange-08)" : "transparent",
    color: actif ? "var(--tcn-orange-deep)" : "var(--tcn-text-muted)",
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

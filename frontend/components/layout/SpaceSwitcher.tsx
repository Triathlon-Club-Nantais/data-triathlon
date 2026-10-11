"use client";

import Link from "next/link";
import { ChevronDown, LayoutGrid } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLinkItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { libelleCompteur } from "@/lib/queries/nav-badges";
import { SPACES, type SpaceId } from "./nav.config";

export type SwitcherSpace = { id: SpaceId; label: string; href: string; count?: number };

/** Mène d'un espace à l'autre ; `compact` : icône seule, pour le rail replié. */
export function SpaceSwitcher({
  current,
  spaces,
  compact = false,
}: {
  current: SpaceId;
  spaces: SwitcherSpace[];
  compact?: boolean;
}) {
  if (spaces.length < 2) return null;
  const nom = `Espace : ${SPACES[current].label}, changer d'espace`;

  const declencheur = (
    <DropdownMenuTrigger
      aria-label={nom}
      className="tcn-btn tcn-btn--sm tcn-btn--secondary"
      style={{ flex: "none" }}
    >
      {compact ? (
        <LayoutGrid size={16} aria-hidden />
      ) : (
        <>
          {SPACES[current].label}
          <ChevronDown size={14} aria-hidden />
        </>
      )}
    </DropdownMenuTrigger>
  );

  return (
    <DropdownMenu>
      {compact ? (
        <Tooltip>
          <TooltipTrigger render={declencheur} />
          <TooltipContent>{nom}</TooltipContent>
        </Tooltip>
      ) : (
        declencheur
      )}
      <DropdownMenuContent align="start" className="w-auto min-w-48">
        {spaces.map((espace) => (
          <DropdownMenuLinkItem
            key={espace.id}
            render={<Link href={espace.href} prefetch={false} />}
            aria-current={espace.id === current ? "true" : undefined}
            className="justify-between gap-3"
          >
            {espace.label}
            {espace.count ? (
              <span style={{ display: "inline-flex" }}>
                <span
                  aria-hidden="true"
                  style={{
                    minWidth: 20,
                    padding: "1px 6px",
                    borderRadius: "var(--tcn-radius-pill)",
                    background: "var(--tcn-orange-deep)",
                    color: "#fff",
                    fontSize: 11,
                    fontWeight: 700,
                    textAlign: "center",
                  }}
                >
                  {espace.count}
                </span>
                <span className="sr-only">{libelleCompteur("backoffice", espace.count)}</span>
              </span>
            ) : null}
          </DropdownMenuLinkItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * En-tête de page homogène : (retour optionnel) + titre + description + slot
 * d'actions. Remplace les `h1` nus pour une hiérarchie cohérente sur tous les écrans.
 */
export function PageHeader({
  title,
  eyebrow,
  description,
  actions,
  backHref,
  backLabel = "Retour",
  className,
  children,
}: {
  title: React.ReactNode;
  eyebrow?: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  backHref?: string;
  backLabel?: string;
  className?: string;
  /** Contenu additionnel sous le titre (badges, méta…). */
  children?: React.ReactNode;
}) {
  return (
    <div className={cn("space-y-3", className)}>
      {backHref && (
        <Link
          href={backHref}
          // `py-1 -my-1` : la cible passe de 20 à 28 px de haut (SC 2.5.8 en
          // demande 24) sans déplacer quoi que ce soit autour.
          className="-my-1 inline-flex items-center gap-1 py-1 text-sm font-medium text-[var(--tcn-text-faint)] transition-colors hover:text-foreground"
        >
          <ChevronLeft className="size-4" />
          {backLabel}
        </Link>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1.5">
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h1 className="font-heading text-[28px] leading-none tracking-tight text-foreground sm:text-[40px]">
            {title}
          </h1>
          {description && (
            <p className="max-w-2xl text-sm text-[var(--tcn-text-faint)]">{description}</p>
          )}
          {children}
        </div>
        {actions && (
          // `flex-wrap` : `.tcn-btn` porte `white-space: nowrap`, donc deux
          // commandes larges (profil athlète) forment un bloc incompressible
          // qui déborde à 360px sans repli à la ligne (WCAG 1.4.10, #488
          // revue UI/UX). `items-start` plutôt que `items-center` : sur ce
          // même profil, une colonne haute (`AthleteSelection`) et un bouton
          // simple (`AthleteAdminPanel`) n'ont de rang commun qu'au sommet.
          <div className="flex shrink-0 flex-wrap items-start gap-2">{actions}</div>
        )}
      </div>
    </div>
  );
}

import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * En-tête de page homogène : (retour optionnel) + titre + description + slot
 * d'actions. Remplace les `h1` nus pour une hiérarchie cohérente sur tous les écrans.
 */
export function PageHeader({
  title,
  description,
  actions,
  backHref,
  backLabel = "Retour",
  className,
  children,
}: {
  title: React.ReactNode;
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
          className="inline-flex items-center gap-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="size-4" />
          {backLabel}
        </Link>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1.5">
          <h1 className="font-heading text-2xl font-bold tracking-tight sm:text-[28px]">
            {title}
          </h1>
          {description && (
            <p className="max-w-2xl text-sm text-muted-foreground">{description}</p>
          )}
          {children}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

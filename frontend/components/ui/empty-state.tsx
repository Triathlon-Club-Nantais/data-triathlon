import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/**
 * SPLIT — état vide. Carte centrée : titre + sous-titre + CTA primaire optionnel.
 */
export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
  bare = false,
}: {
  title: string;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  /** Saute la Card : pour s'insérer dans un conteneur déjà cadré (un `tcn/Card`,
   *  par exemple) plutôt que d'imbriquer deux cartes au rayon différent. */
  bare?: boolean;
}) {
  const contenu = (
    <>
      {icon && <div className="text-muted-foreground [&>svg]:size-8">{icon}</div>}
      <div className="text-base font-bold">{title}</div>
      {description && (
        <div className="max-w-sm text-sm text-[var(--tcn-text-faint)]">{description}</div>
      )}
      {action && <div className="mt-2">{action}</div>}
    </>
  );

  if (bare) {
    return (
      <div className={cn("flex flex-col items-center gap-3 px-6 py-12 text-center", className)}>
        {contenu}
      </div>
    );
  }

  return (
    <Card className={cn("items-center gap-3 px-6 py-12 text-center", className)}>{contenu}</Card>
  );
}

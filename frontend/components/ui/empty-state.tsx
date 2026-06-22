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
}: {
  title: string;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("items-center gap-3 px-6 py-12 text-center", className)}>
      {icon && <div className="text-muted-foreground [&>svg]:size-8">{icon}</div>}
      <div className="text-base font-bold">{title}</div>
      {description && (
        <div className="max-w-sm text-sm text-muted-foreground">{description}</div>
      )}
      {action && <div className="mt-2">{action}</div>}
    </Card>
  );
}

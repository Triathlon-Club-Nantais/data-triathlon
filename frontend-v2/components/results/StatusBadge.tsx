import { Badge } from "@/components/ui/badge";

// Statuts non-finishers porteurs d'un sigle. Un finisher (ou statut inconnu)
// n'affiche aucun badge — le temps total suffit à le signaler.
const NON_FINISHER_LABELS: Record<string, string> = {
  DNS: "Non partant",
  DNF: "Abandon",
  DSQ: "Disqualifié",
};

/**
 * Badge sigle (DNS/DNF/DSQ) pour un non-finisher. Pour un finisher (ou statut
 * inconnu), affiche `fallback` (rien par défaut).
 */
export function StatusBadge({
  status,
  className,
  fallback = null,
}: {
  status: string | null | undefined;
  className?: string;
  fallback?: React.ReactNode;
}) {
  const sigle = (status ?? "").toUpperCase();
  const label = NON_FINISHER_LABELS[sigle];
  if (!label) return <>{fallback}</>;
  return (
    <Badge variant="destructive" className={className} title={label}>
      {sigle}
    </Badge>
  );
}

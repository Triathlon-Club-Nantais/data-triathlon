import { Badge } from "@/components/ui/badge";
import { eventTypeLabel } from "@/lib/constants";

export function SportBadge({ type }: { type: string | null | undefined }) {
  if (!type) return null;
  return <Badge variant="secondary">{eventTypeLabel(type)}</Badge>;
}

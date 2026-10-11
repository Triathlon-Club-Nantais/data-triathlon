import type { ReactNode } from "react";
import { NoAdminAccess } from "@/components/admin/NoAdminAccess";
import { spaceRefusal } from "@/components/layout/space-guard";

/** Garde de l'espace Encadrement (#1297), même conduite que celle de `/admin`. */
export default async function SupervisionLayout({ children }: { children: ReactNode }) {
  const refus = await spaceRefusal("Encadrement", (session) => session.can_supervise, <NoAdminAccess space="encadrement" />);
  if (refus) return refus;
  return children;
}

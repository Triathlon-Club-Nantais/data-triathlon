import type { ReactNode } from "react";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { NoAdminAccess } from "@/components/admin/NoAdminAccess";
import { spaceRefusal } from "@/components/layout/space-guard";

/**
 * Garde de l'espace Encadrement (#1297), même conduite que celle de `/admin`.
 * Monte aussi le dialog des gestes destructifs (#499) : les écrans Jeunes et
 * Bénévolat, venus de `/admin` avec #1336, appellent `useDangerConfirm` (#1783).
 */
export default async function SupervisionLayout({ children }: { children: ReactNode }) {
  const refus = await spaceRefusal("Encadrement", (session) => session.can_supervise, <NoAdminAccess space="encadrement" />);
  if (refus) return refus;
  return <DangerConfirmProvider>{children}</DangerConfirmProvider>;
}

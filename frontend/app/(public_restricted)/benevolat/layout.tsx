import type { ReactNode } from "react";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";

/**
 * Monte le dialog de confirmation partagé (#499) au-dessus de la page de
 * déclaration de bénévolat — nécessaire pour la suppression (US4). Layout
 * dédié plutôt qu'un montage à la racine du site : patron `benevoles/layout.tsx`,
 * un provider inutilisé ailleurs n'a rien à faire au-dessus de tout le site.
 */
export default function BenevolatLayout({ children }: { children: ReactNode }) {
  return <DangerConfirmProvider>{children}</DangerConfirmProvider>;
}

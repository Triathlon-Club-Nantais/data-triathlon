import type { ReactNode } from "react";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { PageHeader } from "@/components/layout/PageHeader";
import { PreviewRefusal, hasPagesPreview } from "@/components/layout/PreviewRefusal";
import { apiServer } from "@/lib/api/server";

/**
 * Monte le dialog de confirmation partagé (#499) au-dessus de la page de
 * déclaration de bénévolat — nécessaire pour la suppression (US4). Layout
 * dédié plutôt qu'un montage à la racine du site : patron `benevoles/layout.tsx`,
 * un provider inutilisé ailleurs n'a rien à faire au-dessus de tout le site.
 *
 * Masquée derrière `pages:preview` (#879), comme la Carte : le club n'a pas
 * encore arrêté l'usage du bénévolat. Rien n'est supprimé.
 */
export default async function BenevolatLayout({ children }: { children: ReactNode }) {
  if (!hasPagesPreview(await apiServer.getSession())) {
    return <PreviewRefusal header={<PageHeader eyebrow="Bénévolat" title="Bénévolat" />} />;
  }
  return <DangerConfirmProvider>{children}</DangerConfirmProvider>;
}

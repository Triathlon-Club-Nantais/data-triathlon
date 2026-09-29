import type { ReactNode } from "react";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { PageHeader } from "@/components/layout/PageHeader";
import { previewGate } from "@/components/layout/PreviewRefusal";
import { EN_TETE_BENEVOLAT } from "@/components/benevolat/en-tete";

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
  const refus = await previewGate(<PageHeader {...EN_TETE_BENEVOLAT} />);
  if (refus) return refus;
  return <DangerConfirmProvider>{children}</DangerConfirmProvider>;
}

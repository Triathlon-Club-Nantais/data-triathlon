import type { Metadata } from "next";
import type { ReactNode } from "react";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";
import { PageHeader } from "@/components/layout/PageHeader";
import { PreviewRefusal, hasPagesPreview } from "@/components/layout/PreviewRefusal";
import { apiServer } from "@/lib/api/server";

export const metadata: Metadata = { title: "Vérification des résultats" };

/**
 * Monte le dialog de confirmation partagé (#499) au-dessus de l'écran
 * bénévole.
 *
 * `DangerConfirmProvider` était jusqu'ici monté uniquement dans
 * `app/admin/layout.tsx`, tous ses appelants étant sous `/admin` — ce n'est
 * plus vrai depuis #490 (revue UI/UX, item 2) : le garde-fou de brouillon sale
 * de `app/benevoles/page.tsx` appelait `window.confirm`, en violation de la
 * règle documentée (`frontend/AGENTS.md`, #499). Un layout dédié, à côté de
 * cette page et non à la racine du site : `/benevoles` reste hors du
 * back-office (sa propre garde d'accès, `AccessGate`, #271), et un provider
 * inutilisé ailleurs n'a rien à faire au-dessus de tout le site.
 */
export default async function BenevolesLayout({ children }: { children: ReactNode }) {
  // Derrière `pages:preview` (#879), avant même la porte bénévoles (`AccessGate`).
  if (!hasPagesPreview(await apiServer.getSession())) {
    return <PreviewRefusal header={<PageHeader eyebrow="Bénévoles" title="Validation des épreuves" />} />;
  }
  return <DangerConfirmProvider>{children}</DangerConfirmProvider>;
}

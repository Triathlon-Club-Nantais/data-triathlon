import type { ReactNode } from "react";
import { DangerConfirmProvider } from "@/components/admin/DangerConfirm";

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
export default function BenevolesLayout({ children }: { children: ReactNode }) {
  return <DangerConfirmProvider>{children}</DangerConfirmProvider>;
}

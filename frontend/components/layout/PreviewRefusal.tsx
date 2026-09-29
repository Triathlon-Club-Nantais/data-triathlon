import type { ReactNode } from "react";
import { PageShell } from "@/components/layout/PageShell";
import { Alert } from "@/components/tcn";

export { hasPagesPreview } from "./nav.config";

/**
 * Ce que rend un écran retiré du grand public à qui n'a pas `pages:preview`
 * (#811, #879). Rendu **à la place** du contenu, jamais par redirection : une
 * redirection muette laissait un compte sans diagnostic (#831).
 */
export function PreviewRefusal({ header }: { header?: ReactNode }) {
  return (
    <PageShell>
      <div className="space-y-8">
        {header}
        <Alert status="error" title="Vous n'avez pas la permission nécessaire">
          Cette page est réservée aux comptes disposant du pouvoir « Voir les pages en
          avant-première ». Si vous pensez qu&apos;il devrait figurer sur votre rôle,
          contactez un administrateur du club.
        </Alert>
      </div>
    </PageShell>
  );
}

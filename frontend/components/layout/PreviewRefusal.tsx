import Link from "next/link";
import type { ReactNode } from "react";
import { PageShell } from "@/components/layout/PageShell";
import { Alert } from "@/components/tcn";
import { ApiError } from "@/lib/api/client";
import { apiServer } from "@/lib/api/server";
import type { SessionUser } from "@/lib/types";
import { unstable_rethrow } from "next/navigation";
import { hasPagesPreview } from "./nav.config";
import { UnavailableScreen } from "./UnavailableScreen";

export { hasPagesPreview } from "./nav.config";

/**
 * Ce que rend un écran retiré du grand public à qui n'a pas `pages:preview`
 * (#811, #879). Rendu **à la place** du contenu, jamais par redirection : une
 * redirection muette laissait un compte sans diagnostic (#831). Un anonyme est
 * invité à se connecter : lui parler de « son rôle » n'aurait pas de sens.
 */
export function PreviewRefusal({ header, session }: { header?: ReactNode; session: SessionUser | null }) {
  return (
    <PageShell>
      <div className="space-y-8">
        {header}
        {session ? (
          <Alert status="error" title="Vous n'avez pas la permission nécessaire">
            Cette page est réservée aux comptes disposant du pouvoir « Voir les pages en
            avant-première ». Si vous pensez qu&apos;il devrait figurer sur votre rôle,
            contactez un administrateur du club.
          </Alert>
        ) : (
          <Alert
            status="warning"
            title="Page en avant-première"
            action={
              <Link
                href="/login"
                className="tcn-cible-tactile inline-flex items-center text-sm font-semibold text-accent-ink underline underline-offset-2"
              >
                Se connecter
              </Link>
            }
          >
            Cette page est réservée aux comptes disposant du pouvoir « Voir les pages en
            avant-première ». Connectez-vous pour y accéder.
          </Alert>
        )}
      </div>
    </PageShell>
  );
}

/**
 * Garde serveur d'un écran `preview` (#879) : `null` pour laisser passer, sinon
 * l'écran à rendre à la place. Une session **illisible** (5xx, réseau) n'est pas
 * une session sans pouvoir : elle rend l'indisponibilité du site plutôt que de
 * lever vers l'écran de plantage ou d'affirmer un refus.
 */
export async function previewGate(header: ReactNode): Promise<ReactNode | null> {
  let session: SessionUser | null;
  try {
    session = await apiServer.getSession();
  } catch (erreur) {
    // Les signaux internes de Next (rendu dynamique, redirection) repartent.
    unstable_rethrow(erreur);
    const statut = erreur instanceof ApiError ? erreur.status : "sans réponse";
    console.error(`[preview] session indisponible (${statut}) : ${erreur}`);
    return <UnavailableScreen />;
  }
  if (hasPagesPreview(session)) return null;
  return <PreviewRefusal header={header} session={session} />;
}

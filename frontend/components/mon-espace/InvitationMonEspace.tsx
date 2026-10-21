"use client";

import Link from "next/link";
import { nomComplet, OPEN_PICKER_EVENT } from "@/components/layout/AthletePicker";
import { Card } from "@/components/tcn";
import type { SessionUser } from "@/lib/types";

/**
 * Mon espace est réservé au membre connecté dont le compte est rattaché à sa
 * fiche (#1325) : le visiteur est invité à se connecter, le compte non rattaché
 * à trouver sa fiche (palette), puis « C'est moi » sur la fiche.
 */
export function InvitationMonEspace({ session }: { session: SessionUser | null }) {
  const demande = session?.athlete_claim ?? null;
  return (
    <Card>
      <p style={{ margin: 0 }}>
        Mon espace réunit vos chiffres et vos résultats. Il est réservé aux membres du club dont le compte est rattaché à
        leur fiche d&apos;athlète.
      </p>
      <div style={{ marginTop: 14 }}>
        {session === null ? (
          <Link href="/login" className="tcn-cible-tactile inline-flex items-center font-semibold underline underline-offset-2">
            Se connecter
          </Link>
        ) : demande?.status === "pending" ? (
          <p role="status" style={{ margin: 0, color: "var(--tcn-text-muted)" }}>
            Votre demande de rattachement à la fiche de {nomComplet(demande.athlete)} est en attente : le club la valide.
          </p>
        ) : !session.is_member ? (
          <>
            <p style={{ margin: "0 0 8px", color: "var(--tcn-text-muted)" }}>Mon espace est réservé aux adhérents du club.</p>
            <Link href="/mon-compte#adhesion" className="tcn-cible-tactile inline-flex items-center font-semibold underline underline-offset-2">
              {session.member_request?.status === "pending"
                ? "Votre demande d'adhésion est en attente de validation."
                : "Demander à rejoindre le club"}
            </Link>
          </>
        ) : (
          <>
            {demande?.status === "rejected" && (
              <p style={{ margin: "0 0 8px", color: "var(--tcn-text-muted)" }}>Votre précédente demande a été refusée.</p>
            )}
            <button
              type="button"
              onClick={() => window.dispatchEvent(new Event(OPEN_PICKER_EVENT))}
              className="tcn-cible-tactile inline-flex items-center font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--tcn-orange)]"
            >
              Trouvez votre fiche, puis demandez le rattachement avec « C&apos;est moi » →
            </button>
          </>
        )}
      </div>
    </Card>
  );
}

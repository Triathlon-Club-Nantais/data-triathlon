"use client";

import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Input } from "@/components/tcn";
import { CLUB_NAME_SHORT } from "@/lib/club";
import { useCancelMembershipRequest, useRequestMembership } from "@/lib/queries/auth";
import type { SessionUser } from "@/lib/types";

const TITRE = { fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: "0 0 12px" } as const;
const DISCRET = { margin: 0, color: "var(--tcn-text-muted)" } as const;
const LABEL = { display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6, color: "var(--tcn-text-body)" } as const;

function Champ({ id, label, ...rest }: { id: string; label: string } & React.ComponentProps<typeof Input>) {
  return (
    <div>
      <label htmlFor={id} style={LABEL}>{label}</label>
      <Input id={id} style={{ width: "100%" }} {...rest} />
    </div>
  );
}

const ID_ERREUR = "adhesion-erreur";
const DELAI_NOUVELLE_DEMANDE_JOURS = 30;

/** Date (JJ/MM/AAAA) à partir de laquelle une nouvelle demande est permise, ou `null` si le délai est écoulé. */
function finDuRefus(decidedAt: string): string | null {
  const fin = new Date(decidedAt);
  fin.setUTCDate(fin.getUTCDate() + DELAI_NOUVELLE_DEMANDE_JOURS);
  fin.setUTCHours(0, 0, 0, 0);
  return fin.getTime() > Date.now() ? fin.toLocaleDateString("fr-FR", { timeZone: "UTC" }) : null;
}

/** Demande d'adhésion d'un connecté non adhérent (#1785) : le club la valide ou la refuse. */
export function MemberRequestCard({ session }: { session: SessionUser }) {
  const demander = useRequestMembership();
  const annuler = useCancelMembershipRequest();
  const demande = session.member_request;
  const [erreurLocale, setErreurLocale] = useState<{ texte: string; champs: string[] } | null>(null);
  const titre = useRef<HTMLHeadingElement>(null);
  const statut = demande?.status;
  const precedent = useRef(statut);
  useEffect(() => {
    if (precedent.current !== statut) titre.current?.focus();
    precedent.current = statut;
  }, [statut]);
  const finRefus = demande?.status === "rejected" && demande.decided_at ? finDuRefus(demande.decided_at) : null;

  if (demande?.status === "pending") {
    return (
      <Card id="adhesion">
        <h2 ref={titre} tabIndex={-1} style={TITRE}>Adhésion au club</h2>
        <p role="status" style={DISCRET}>
          Votre demande d&apos;adhésion est en attente : un administrateur du club la valide.
        </p>
        <div style={{ marginTop: 12 }}>
          <Button
            variant="secondary"
            aria-disabled={annuler.isPending || undefined}
            onClick={() => {
              if (!annuler.isPending) annuler.mutate();
            }}
          >
            Annuler la demande
          </Button>
        </div>
        {annuler.error && (
          <div role="alert" style={{ marginTop: 12 }}>
            <Alert status="error" title="Annulation impossible">{annuler.error.message}</Alert>
          </div>
        )}
      </Card>
    );
  }

  function echec(texte: string, champs: string[]) {
    setErreurLocale({ texte, champs });
    document.getElementById(champs[0])?.focus();
  }

  function soumettre(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (demander.isPending) return;
    const data = new FormData(event.currentTarget);
    const lire = (name: string) => String(data.get(name) ?? "").trim();
    const first_name = lire("first_name");
    const last_name = lire("last_name");
    if (!first_name || !last_name) {
      return echec("Indiquez votre prénom et votre nom.", [
        ...(first_name ? [] : ["adhesion-prenom"]),
        ...(last_name ? [] : ["adhesion-nom"]),
      ]);
    }
    const birth_date = lire("birth_date") || null;
    const phone = lire("phone") || null;
    if (!birth_date && !phone) {
      return echec("Indiquez votre date de naissance ou votre téléphone.", ["adhesion-naissance", "adhesion-telephone"]);
    }
    setErreurLocale(null);
    demander.mutate({ first_name, last_name, birth_date, phone });
  }

  const erreur = erreurLocale?.texte ?? demander.error?.message;
  const invalide = (id: string) =>
    erreurLocale?.champs.includes(id) ? { "aria-invalid": true as const, "aria-describedby": ID_ERREUR } : {};
  return (
    <Card id="adhesion">
      <h2 ref={titre} tabIndex={-1} style={TITRE}>Adhésion au club</h2>
      {finRefus ? (
        <p style={DISCRET}>
          Votre précédente demande a été refusée. Vous pourrez en envoyer une nouvelle à partir du {finRefus}.
        </p>
      ) : (
        <>
        {demande?.status === "rejected" && <p style={{ ...DISCRET, marginBottom: 8 }}>Votre précédente demande a été refusée.</p>}
        <p style={{ ...DISCRET, marginBottom: 16 }}>
          Ces informations permettent au club de vérifier votre demande ou de vous recontacter. Indiquez votre date de
          naissance ou votre téléphone.
        </p>
        <form onSubmit={soumettre} className="space-y-4" style={{ maxWidth: 380 }}>
          <Champ id="adhesion-prenom" label="Prénom" name="first_name" required autoComplete="given-name" {...invalide("adhesion-prenom")} />
          <Champ id="adhesion-nom" label="Nom" name="last_name" required autoComplete="family-name" {...invalide("adhesion-nom")} />
          <Champ id="adhesion-naissance" label="Date de naissance" name="birth_date" type="date" autoComplete="bday" {...invalide("adhesion-naissance")} />
          <Champ id="adhesion-telephone" label="Téléphone" name="phone" type="tel" autoComplete="tel" {...invalide("adhesion-telephone")} />
          <Button type="submit" aria-disabled={demander.isPending || undefined}>
            {demander.isPending ? "Envoi…" : `Demander à rejoindre le ${CLUB_NAME_SHORT}`}
          </Button>
          {erreur && (
            <div role="alert" id={ID_ERREUR}>
              <Alert status="error" title="Demande non envoyée">{erreur}</Alert>
            </div>
          )}
        </form>
        </>
      )}
    </Card>
  );
}

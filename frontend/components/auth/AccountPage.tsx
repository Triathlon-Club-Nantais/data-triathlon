"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { nomComplet } from "@/components/layout/AthletePicker";
import { Button, Card } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { useCancelAthleteClaim, useDeleteAccount, useDetachAthlete, useMyIdentities, useSession } from "@/lib/queries/auth";
import type { SessionUser } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

const TITRE = { fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: "0 0 12px" } as const;
const DISCRET = { margin: 0, color: "var(--tcn-text-muted)" } as const;
const ERREUR = { margin: 0, color: "var(--tcn-danger-text)" } as const;
const LIEN = "font-semibold text-accent-ink hover:underline";

/** Page « Mon compte » (#1663) : identité, fiche rattachée, suppression. */
export function AccountPage() {
  const { data: session, isPending, errorUpdateCount, refetch, isFetching } = useSession();
  const router = useRouter();
  // Ici et non dans `Compte` : démonté dès que la session passe à null, il ferait sauter le rappel de `mutate`.
  const suppression = useDeleteAccount();

  // Même lecture que `UserMenu` (#954) : sans `data`, une relance repasse en `pending`.
  if (session === undefined && errorUpdateCount > 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <p role="alert" style={DISCRET}>Votre session est indisponible pour le moment.</p>
        <Button
          variant="secondary"
          size="sm"
          aria-disabled={isFetching || undefined}
          onClick={() => {
            if (!isFetching) void refetch();
          }}
        >
          {isFetching ? "Nouvelle tentative…" : "Réessayer"}
        </Button>
      </div>
    );
  }
  if (isPending) {
    return (
      <div data-testid="squelette-compte" className="space-y-6">
        <Skeleton className="h-48 w-full rounded-lg" />
        <Skeleton className="h-32 w-full rounded-lg" />
      </div>
    );
  }
  // Compte supprimé : la session relue est anonyme, la redirection vers l'accueil est en cours.
  if (suppression.isSuccess) return null;
  // Sans moyen de connexion configuré, la garde laisse passer un anonyme.
  if (!session) {
    return (
      <p style={DISCRET}>
        <Link href="/login" className="underline underline-offset-2">Connectez-vous</Link> pour gérer votre compte.
      </p>
    );
  }
  return (
    <Compte
      session={session}
      suppression={suppression}
      onSupprimer={() => suppression.mutate(undefined, { onSuccess: () => router.push("/") })}
    />
  );
}

function Compte({
  session,
  suppression,
  onSupprimer,
}: {
  session: SessionUser;
  suppression: ReturnType<typeof useDeleteAccount>;
  onSupprimer: () => void;
}) {
  const [suppressionOuverte, setSuppressionOuverte] = useState(false);
  const detachement = useDetachAthlete();
  const [detachementOuvert, setDetachementOuvert] = useState(false);
  const annulation = useCancelAthleteClaim();
  const demande = session.athlete_claim;

  return (
    <div className="space-y-6">
      <Card>
        <h2 style={TITRE}>Mes informations</h2>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[max-content_1fr]" style={{ margin: 0 }}>
          <dt style={DISCRET}>Adresse</dt>
          <dd style={{ margin: 0, overflowWrap: "anywhere" }}>{session.email}</dd>
          <dt style={DISCRET}>Nom affiché</dt>
          <dd style={{ margin: 0 }}>{session.display_name}</dd>
          <dt style={DISCRET}>Statut</dt>
          <dd style={{ margin: 0 }}>{session.is_member ? "Adhérent" : "Non adhérent"}</dd>
          <dt style={DISCRET}>Connexions</dt>
          <dd style={{ margin: 0 }}>
            <Connexions />
          </dd>
        </dl>
        <p style={{ ...DISCRET, marginTop: 16, fontSize: 14 }}>Compte créé le {formatDate(session.created_at)}</p>
      </Card>

      <Card>
        <h2 style={TITRE}>Fiche athlète</h2>
        {session.athlete ? (
          <div className="space-y-3">
            <p style={{ margin: 0, fontWeight: 700 }}>{nomComplet(session.athlete)}</p>
            <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <Link href="/mon-espace" className={LIEN}>Ouvrir Mon espace</Link>
              <Button
                variant="secondary"
                onClick={() => {
                  detachement.reset();
                  setDetachementOuvert(true);
                }}
              >
                Me détacher de ma fiche
              </Button>
            </div>
            <DangerConfirm
              open={detachementOuvert}
              onOpenChange={setDetachementOuvert}
              titre="Vous détacher de votre fiche ?"
              description={
                <>
                  Votre compte ne sera plus lié à la fiche de {nomComplet(session.athlete)}, qui reste publiée avec ses
                  résultats. Pour la rattacher de nouveau, il faudra une nouvelle demande validée par le club.
                </>
              }
              libelleAction="Me détacher"
              avertissement={detachement.error?.message}
              enAttente={detachement.isPending}
              onConfirm={() => detachement.mutate(undefined, { onSuccess: () => setDetachementOuvert(false) })}
            />
          </div>
        ) : demande?.status === "pending" ? (
          <div className="space-y-3">
            <p style={{ margin: 0 }}>Demande en attente : {nomComplet(demande.athlete)}</p>
            <Button variant="secondary" disabled={annulation.isPending} onClick={() => annulation.mutate()}>
              Annuler la demande
            </Button>
            {annulation.error && <p role="alert" style={ERREUR}>{annulation.error.message}</p>}
          </div>
        ) : demande ? (
          <div className="space-y-3">
            <p style={{ margin: 0 }}>Demande refusée : {nomComplet(demande.athlete)}</p>
            <Link href="/mon-espace" className={LIEN}>Faire une nouvelle demande depuis Mon espace</Link>
          </div>
        ) : (
          <p style={DISCRET}>
            Aucune fiche athlète n&apos;est rattachée à votre compte.{" "}
            <Link href="/mon-espace" className="underline underline-offset-2">Rattacher ma fiche depuis Mon espace</Link>
          </p>
        )}
      </Card>

      <Card style={{ borderColor: "var(--tcn-danger-border)" }}>
        <h2 style={TITRE}>Zone sensible</h2>
        <Button
          variant="destructive"
          onClick={() => {
            suppression.reset();
            setSuppressionOuverte(true);
          }}
        >
          Supprimer mon compte
        </Button>
        <DangerConfirm
          open={suppressionOuverte}
          onOpenChange={setSuppressionOuverte}
          titre="Supprimer votre compte ?"
          description={
            <>
              Votre compte, vos connexions, rôles et groupes sont effacés. Vos résultats et votre fiche athlète
              restent publiés. Vous pourrez vous reconnecter plus tard : un compte neuf, sans rôle, sera créé.
            </>
          }
          avertissement={suppression.error?.message}
          enAttente={suppression.isPending}
          onConfirm={onSupprimer}
        />
      </Card>
    </div>
  );
}

/** Fournisseurs liés au compte, monté seulement pour une session ouverte (401 sinon). */
function Connexions() {
  const { data, isPending, error, refetch, isFetching } = useMyIdentities();
  if (isPending) return <Skeleton className="h-5 w-48" />;
  if (error) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <p role="alert" style={ERREUR}>Connexions indisponibles pour le moment.</p>
        <Button
          variant="secondary"
          size="sm"
          aria-disabled={isFetching || undefined}
          onClick={() => {
            if (!isFetching) void refetch();
          }}
        >
          {isFetching ? "Nouvelle tentative…" : "Réessayer"}
        </Button>
      </div>
    );
  }
  if (data.length === 0) return <span style={DISCRET}>Aucune connexion enregistrée.</span>;
  return (
    <ul style={{ margin: 0, padding: 0, listStyle: "none" }} className="space-y-1">
      {data.map((identite) => (
        <li key={`${identite.provider}-${identite.created_at}`}>
          <strong>{identite.label}</strong>{" "}
          <span style={{ color: "var(--tcn-text-muted)", overflowWrap: "anywhere" }}>{identite.email}</span>
        </li>
      ))}
    </ul>
  );
}

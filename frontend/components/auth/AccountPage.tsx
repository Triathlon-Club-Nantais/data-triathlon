"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { nomComplet } from "@/components/layout/AthletePicker";
import { ContactEmail } from "@/components/legal/blocks";
import { Button, Card } from "@/components/tcn";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, apiClient } from "@/lib/api/client";
import {
  useApplyMyOpposition,
  useCancelAthleteClaim,
  useDeleteAccount,
  useDetachAthlete,
  useMyIdentities,
  useSession,
} from "@/lib/queries/auth";
import type { OppositionPreview, SessionUser } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";
import { motCompte, plural } from "@/lib/utils/format";

const TITRE = { fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: "0 0 12px" } as const;
const DISCRET = { margin: 0, color: "var(--tcn-text-muted)" } as const;
const ERREUR = { margin: 0, color: "var(--tcn-danger-text)" } as const;
const LIEN = "font-semibold text-accent-ink hover:underline";

function messageAnonymise(resultats: number): string {
  if (resultats === 0) return "Vos résultats sont anonymisés.";
  return `Vos résultats sont anonymisés. ${motCompte(resultats, "résultat")} ${plural(resultats, "ne porte", "ne portent")} plus votre nom.`;
}

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
  const opposition = useApplyMyOpposition();
  const [oppositionOuverte, setOppositionOuverte] = useState(false);
  const [apercu, setApercu] = useState<OppositionPreview | null>(null);
  const [apercuEchoue, setApercuEchoue] = useState(false);

  async function ouvrirOpposition() {
    opposition.reset();
    setApercu(null);
    setApercuEchoue(false);
    setOppositionOuverte(true);
    try {
      setApercu(await apiClient.previewMyOpposition());
    } catch {
      setApercuEchoue(true);
    }
  }

  // Un 409 (homonyme, licencié au même nom rattaché ailleurs) se traite comme un aperçu qui renvoie au club.
  const refusParLeClub = opposition.error instanceof ApiError && opposition.error.status === 409;
  const versLeClub = apercu !== null && (apercu.athletes !== 1 || apercu.already_opposed || refusParLeClub);
  const erreurOpposition = apercuEchoue
    ? "Les résultats concernés n'ont pas pu être comptés. Fermez puis rouvrez pour réessayer."
    : refusParLeClub
      ? undefined
      : opposition.error?.message;
  // Le bouton quitte le DOM avec la fiche : le focus va au message de succès, sinon il retomberait sur `<body>`.
  const statut = useRef<HTMLParagraphElement>(null);
  const anonymisee = useRef(false);

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

      <Card>
        <h2 style={TITRE}>Mes données</h2>
        <p style={{ ...DISCRET, marginBottom: 12 }}>
          Une copie de votre compte, de vos connexions, demandes, objectifs, déclarations de bénévolat et des
          résultats de votre fiche, dans un fichier JSON.
        </p>
        <a href="/api/v1/auth/me/export" download className="tcn-btn tcn-btn--secondary tcn-cible-tactile">
          Télécharger mes données
        </a>
      </Card>

      <Card style={{ borderColor: "var(--tcn-danger-border)" }}>
        <h2 style={TITRE}>Zone sensible</h2>
        <p ref={statut} role="status" tabIndex={-1} className="mb-3 empty:mb-0">
          {opposition.isSuccess && apercu ? messageAnonymise(apercu.results) : ""}
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          {session.athlete && (
            <Button variant="destructive" onClick={() => void ouvrirOpposition()}>
              Anonymiser mes résultats
            </Button>
          )}
          <DangerConfirm
            open={oppositionOuverte}
            onOpenChange={setOppositionOuverte}
            titre="Anonymiser vos résultats ?"
            description={
              !apercu ? (
                !apercuEchoue && "Calcul des résultats concernés…"
              ) : versLeClub ? (
                <>
                  {(apercu.athletes > 1 || refusParLeClub) &&
                    "Votre nom est partagé avec une autre personne connue du club. "}
                  Écrivez au club à <ContactEmail /> pour exercer votre droit d&apos;opposition.
                </>
              ) : (
                <>
                  Cette action est définitive.{" "}
                  {apercu.results === 0
                    ? "Aucun résultat publié à votre nom pour l'instant."
                    : `${motCompte(apercu.results, "résultat")} ${plural(apercu.results, "devient anonyme", "deviennent anonymes")} : votre nom, votre club et votre catégorie disparaissent, le temps et le rang restent.`}{" "}
                  Votre fiche athlète et son lien avec votre compte sont supprimés. Votre compte reste actif. La
                  fiche et le nom ne peuvent pas être rétablis. Pour publier à nouveau vos prochains résultats,
                  écrivez au club.
                </>
              )
            }
            avertissement={erreurOpposition && <span role="alert" style={ERREUR}>{erreurOpposition}</span>}
            actionBloquee={!apercu || versLeClub}
            libelleAction="Anonymiser définitivement"
            enAttente={opposition.isPending}
            onConfirm={() =>
              opposition.mutate(undefined, {
                onSuccess: () => {
                  anonymisee.current = true;
                  setOppositionOuverte(false);
                },
              })
            }
            finalFocus={() => (anonymisee.current ? (statut.current ?? true) : true)}
          />
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
        </div>
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

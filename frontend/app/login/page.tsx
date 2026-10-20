"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId } from "react";
import { captureEvent, withPostHog } from "@/lib/posthog";
import { Alert, Button, Card, Eyebrow } from "@/components/tcn";
import { messageDeRefus } from "@/lib/api/refus";
import { authErrorLabel } from "@/lib/constants";
import { useAuthMethods } from "@/lib/queries/auth";
import type { AuthMethod } from "@/lib/types";

/**
 * `useSearchParams` impose une frontière Suspense : sans elle, le build de
 * production échoue sur le prérendu statique de cette page, qui n'a par ailleurs
 * aucune raison d'être dynamique.
 */
export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <Connexion />
    </Suspense>
  );
}

function Connexion() {
  const { data: methodes, isPending, isError, error, refetch } = useAuthMethods();
  const erreur = useSearchParams().get("error");
  const idAdherent = useId();
  const idAdmin = useId();
  // posthog-js chargé dès l'affichage (#1394) : chargé au clic, `login_initiated` partirait après
  // la navigation du lien, donc jamais.
  useEffect(() => withPostHog(() => {}), []);

  // Le public de chaque méthode vient du backend (#1666), jamais d'un slug codé ici.
  const adherents = methodes?.filter((methode) => methode.audience === "member") ?? [];
  const admins = methodes?.filter((methode) => methode.audience === "admin") ?? [];

  return (
    <div className="mx-auto my-16 max-w-[460px] px-4">
      <Card>
        <Eyebrow id={idAdherent}>Espace adhérent</Eyebrow>
        <h1 className="font-display mt-1.5 mb-1 text-[30px] text-[var(--tcn-ink)]">Connexion</h1>
        <p className="mb-5 text-sm text-[var(--tcn-text-muted)]">
          La connexion adhérent ouvre votre espace personnel : vos résultats, vos objectifs et
          votre page d&apos;athlète. Les résultats du club se consultent aussi sans compte, avec
          le code d&apos;accès du club.
        </p>

        {erreur && (
          <div className="mb-4">
            <Alert status="error">{authErrorLabel(erreur)}</Alert>
          </div>
        )}

        {isPending && <p className="text-sm text-[var(--tcn-text-faint)]">Chargement…</p>}

        {isError && (
          <div className="mb-4">
            {(() => {
              const { title, description } = messageDeRefus(error, {
                sujet: "moyens de connexion",
                action: "consulter les moyens de connexion",
              });
              return (
                <Alert
                  status="error"
                  title={title}
                  action={
                    <Button variant="secondary" size="sm" onClick={() => refetch()}>
                      Réessayer
                    </Button>
                  }
                >
                  {description}
                </Alert>
              );
            })()}
          </div>
        )}

        {!isPending && !isError && methodes?.length === 0 && (
          <Alert status="warning">
            Aucun moyen de connexion n&apos;est disponible sur ce site pour le moment.
          </Alert>
        )}

        {adherents.length === 0 && admins.length > 0 && (
          <Alert status="warning">
            La connexion adhérent n&apos;est pas encore disponible sur ce site. Les résultats du
            club se consultent avec le code d&apos;accès.
          </Alert>
        )}

        {adherents.length > 0 && (
          <section aria-labelledby={idAdherent} className="flex flex-col gap-2.5">
            {adherents.map((methode) => (
              <LienFournisseur key={methode.slug} methode={methode} variant="primary" />
            ))}
          </section>
        )}
      </Card>

      {admins.length > 0 && (
        <section
          aria-labelledby={idAdmin}
          className="mt-8 flex flex-col gap-2.5 px-7 text-sm text-[var(--tcn-text-muted)]"
        >
          <h2 id={idAdmin} className="text-base font-bold text-[var(--tcn-text-body)]">
            Administration
          </h2>
          <p>Réservé aux administrateurs du site.</p>
          {admins.map((methode) => (
            <LienFournisseur key={methode.slug} methode={methode} variant="secondary" />
          ))}
        </section>
      )}
    </div>
  );
}

/**
 * Un lien et non un bouton : le parcours est une navigation vers le backend, qui
 * répond par une redirection vers le fournisseur.
 */
function LienFournisseur({
  methode,
  variant,
}: {
  methode: AuthMethod;
  variant: "primary" | "secondary";
}) {
  return (
    <a
      href={`/api/v1/auth/${methode.slug}/authorize`}
      onClick={() =>
        // La navigation vers /authorize démarre dès ce clic : sendBeacon
        // survit au unload, send_instantly saute la file batchée qui,
        // sinon, perdrait l'événement (cf. revue #339).
        captureEvent("login_initiated", { provider: methode.slug }, {
          transport: "sendBeacon",
          send_instantly: true,
        })
      }
      // `.tcn-btn` ne passe pas à la ligne : un libellé long déborderait à 360 px.
      className={`tcn-btn tcn-btn--md tcn-btn--${variant} w-full whitespace-normal text-center leading-tight`}
    >
      Continuer avec {methode.label}
    </a>
  );
}

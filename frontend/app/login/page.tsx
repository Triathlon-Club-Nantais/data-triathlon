"use client";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Alert, Card, Eyebrow } from "@/components/tcn";
import { authErrorLabel } from "@/lib/constants";
import { useAuthMethods } from "@/lib/queries/auth";

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
  const { data: methodes, isPending } = useAuthMethods();
  const erreur = useSearchParams().get("error");

  return (
    <div style={{ maxWidth: 460, margin: "64px auto", padding: "0 16px" }}>
      <Card>
        <Eyebrow>Espace contributeur</Eyebrow>
        <h1
          style={{
            fontFamily: "var(--tcn-font-display)",
            fontSize: 30,
            margin: "6px 0 4px",
            color: "var(--tcn-ink)",
          }}
        >
          Connexion
        </h1>
        <p style={{ color: "var(--tcn-text-muted)", fontSize: 14, marginBottom: 20 }}>
          Le site reste entièrement consultable sans compte. La connexion ne sert
          qu&apos;aux outils réservés aux contributeurs du club.
        </p>

        {erreur && (
          <div style={{ marginBottom: 16 }}>
            <Alert status="error">{authErrorLabel(erreur)}</Alert>
          </div>
        )}

        {isPending && (
          <p style={{ color: "var(--tcn-text-faint)", fontSize: 14 }}>Chargement…</p>
        )}

        {!isPending && methodes?.length === 0 && (
          <Alert status="warning">
            Aucun moyen de connexion n&apos;est disponible sur ce site pour le moment.
          </Alert>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {/* Un lien et non un bouton : le parcours est une navigation vers le
              backend, qui répond par une redirection vers le fournisseur. */}
          {methodes?.map((methode) => (
            <a
              key={methode.slug}
              href={`/api/v1/auth/${methode.slug}/authorize`}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 10,
                padding: "12px 16px",
                borderRadius: "var(--tcn-radius-lg)",
                background: "var(--tcn-ink)",
                color: "#fff",
                fontWeight: 700,
                fontSize: 15,
                textDecoration: "none",
              }}
            >
              Continuer avec {methode.label}
            </a>
          ))}
        </div>
      </Card>
    </div>
  );
}

"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";

/** Footer discret rendant les versions front + back (#134).
 *
 *  Utilité : quand un utilisateur remonte un bug, on veut savoir si son bundle
 *  et le serveur qu'il tape sont sur la même version. Un rollback qui n'a
 *  touché qu'un des deux (Render only, ou Vercel only) doit être visible.
 *
 *  - Front : `NEXT_PUBLIC_APP_VERSION`, embed au build. Instant.
 *  - Back : fetch `/api/v1/version` au montage (une seule requête par page).
 *
 *  États rendus :
 *  - avant fetch : `v0.1.3` (juste la version front, sans « chargement… »
 *    qui clignoterait pour rien).
 *  - front == back : `v0.1.3` (silencieux, cohérent).
 *  - front != back : `front v0.1.3 · back v0.1.2` — le signal utile, en
 *    warning-text pour attirer l'œil sans crier.
 *  - fetch en échec : affiche `v0.1.3 · back ?` (l'utilisateur voit au moins
 *    sa version). Pas de retry : le back peut être injoignable, ce n'est
 *    pas notre affaire ici.
 */
export function VersionFooter() {
  // Version du front embarquée au build par Next.js. Injectée par le workflow
  // `deploy.yml` (`NEXT_PUBLIC_APP_VERSION=${github.ref_name}` pour la prod).
  // `NEXT_PUBLIC_*` est **remplacé au build** par Next — chaque déploiement
  // fige sa propre valeur dans le bundle. En dev / test, on retombe sur "dev".
  const frontVersion = process.env.NEXT_PUBLIC_APP_VERSION || "dev";

  const [backVersion, setBackVersion] = useState<string | null | undefined>(
    undefined,
  );

  useEffect(() => {
    let cancelled = false;
    apiClient
      .getVersion()
      .then((v) => {
        if (!cancelled) setBackVersion(v.version);
      })
      .catch(() => {
        if (!cancelled) setBackVersion(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const mismatch =
    backVersion != null && backVersion !== "" && backVersion !== frontVersion;

  const baseStyle = {
    padding: "16px 20px 20px",
    fontSize: 12,
    color: "var(--tcn-text-faint)",
    textAlign: "center" as const,
    fontFamily: "var(--tcn-font-cond)",
    letterSpacing: "0.02em",
  };

  if (mismatch) {
    return (
      <footer style={{ ...baseStyle, color: "var(--tcn-warning-text)" }}>
        front <b>{frontVersion}</b> · back <b>{backVersion}</b>
      </footer>
    );
  }

  // Fetch encore en cours (backVersion === undefined) ou versions cohérentes
  // (backVersion === frontVersion) : on rend juste la version front. Silencieux
  // et non-clignotant.
  if (backVersion === null) {
    return (
      <footer style={baseStyle}>
        <b>{frontVersion}</b> · back ?
      </footer>
    );
  }
  return (
    <footer style={baseStyle}>
      <b>{frontVersion}</b>
    </footer>
  );
}

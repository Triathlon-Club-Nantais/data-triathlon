"use client";
import "./globals.css";
import type { CSSProperties } from "react";
import { ErrorScreen } from "@/components/tcn/ErrorScreen";
import { FeedbackButton } from "@/components/tcn/FeedbackButton";
import { PageShell } from "@/components/layout/PageShell";

/**
 * Les trois variables que `next/font` poserait sur `<html>` via le layout racine.
 * Sans elles, `--tcn-font-body` (`var(--font-barlow), system-ui, sans-serif`)
 * devient invalide à la substitution — la spec CSS empoisonne **toute** la
 * déclaration, donc la queue `system-ui` n'est jamais atteinte et le dernier
 * filet du site s'afficherait dans le serif par défaut du navigateur.
 */
const POLICES_DE_SECOURS = {
  "--font-anton": "system-ui",
  "--font-barlow": "system-ui",
  "--font-barlow-cond": "system-ui",
} as CSSProperties;

/**
 * Frontière d'erreur du layout racine — le dernier filet.
 *
 * Elle **remplace** `app/layout.tsx`, donc rien de ce qu'il monte n'est là :
 * ni `<html lang="fr">`, ni les tokens `--tcn-*`, ni `AppNav`, ni `Providers`,
 * ni le bouton de signalement. D'où le document complet ci-dessous, l'import
 * explicite de `globals.css`, et le `FeedbackButton` monté ici (il ne dépend
 * d'aucun contexte : `useState`, `apiClient` et `captureEvent`, rien de plus).
 *
 * Deux absences délibérées :
 *
 * - **Pas de `next/font`.** Les trois familles du layout racine coûteraient
 *   trois requêtes de plus sur l'écran qui s'affiche justement parce que tout va
 *   mal. Recommandation de la doc Next 16 pour ce fichier — mais elle ne suffit
 *   pas : il faut *aussi* déclarer les variables absentes (voir
 *   `POLICES_DE_SECOURS`), sinon le repli ne s'applique pas.
 * - **Pas de `metadata`.** Une frontière d'erreur est un composant client, où
 *   l'export est ignoré : le titre passe par le `<title>` de React 19.
 */
export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <html lang="fr" style={POLICES_DE_SECOURS}>
      <body
        className="min-h-screen text-foreground antialiased"
        style={{ background: "var(--tcn-paper)", fontFamily: "var(--tcn-font-body)" }}
      >
        <title>Erreur — TCN</title>
        <main>
          <PageShell>
            <ErrorScreen onRetry={retry} digest={error.digest} />
          </PageShell>
        </main>
        <FeedbackButton />
      </body>
    </html>
  );
}

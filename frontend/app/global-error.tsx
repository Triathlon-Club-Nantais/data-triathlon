"use client";
import "./globals.css";
import { ErrorScreen } from "@/components/tcn/ErrorScreen";
import { FeedbackButton } from "@/components/tcn/FeedbackButton";

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
 *   mal ; `--tcn-font-body` retombe sur `system-ui`. Recommandation de la doc
 *   Next 16 pour ce fichier.
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
    <html lang="fr">
      <body
        className="min-h-screen text-foreground antialiased"
        style={{ background: "var(--tcn-paper)", fontFamily: "var(--tcn-font-body)" }}
      >
        <title>Erreur — TCN</title>
        <main className="mx-auto px-4 pt-6 pb-16 sm:px-8">
          <ErrorScreen onRetry={retry} digest={error.digest} />
        </main>
        <FeedbackButton />
      </body>
    </html>
  );
}

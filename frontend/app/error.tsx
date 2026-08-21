"use client";
import { useEffect } from "react";
import { ErrorScreen } from "@/components/tcn/ErrorScreen";
import { PageShell } from "@/components/layout/PageShell";
import { captureEvent } from "@/lib/posthog";

/**
 * Frontière d'erreur des pages — tout ce qui est sous le layout racine.
 *
 * Trois choix qui ne se re-tranchent pas sans relire `ETAT-1` :
 *
 * - **`retry()`, pas `reset()`** (prop stable depuis Next 16.3). `reset()` vide
 *   l'état de la frontière et re-rend *sans* refaire le fetch : sur la panne la
 *   plus fréquente ici — le réveil à froid du backend Render — « Réessayer »
 *   refaisait donc exactement la même chose. `retry()` refait la requête.
 * - **`error.message` n'est jamais rendu.** En production Next.js y substitue
 *   son paragraphe anglais sur le `digest` ; en développement il peut porter des
 *   détails serveur. Seul le `digest` sort, et il sert au signalement.
 * - **Pas de `FeedbackButton` ici.** Le layout racine survit à cette frontière,
 *   son bouton flottant est donc déjà à l'écran ; un second exemplaire les
 *   empilerait. `global-error.tsx`, qui remplace le layout, porte le sien.
 *
 * `instrumentation-client.ts` remonte déjà les exceptions non rattrapées
 * (`capture_exceptions`). L'événement ci-dessous est autre chose : il mesure
 * combien de visiteurs *voient* l'écran de panne, et le rattache au `digest`
 * qu'ils recopieront dans un signalement.
 */
export default function ErrorBoundary({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    captureEvent("error_screen_shown", { digest: error.digest ?? null });
  }, [error.digest]);

  return (
    <PageShell>
      <ErrorScreen onRetry={retry} digest={error.digest} />
    </PageShell>
  );
}

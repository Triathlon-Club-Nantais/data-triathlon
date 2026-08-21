"use client";
import { ErrorScreen } from "@/components/tcn/ErrorScreen";
import { PageShell } from "@/components/layout/PageShell";

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
 * La mesure PostHog de l'affichage vit dans `ErrorScreen`, pour que
 * `global-error.tsx` la porte aussi : c'est la panne la plus grave et c'était la
 * moins comptée.
 */
export default function ErrorBoundary({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <PageShell>
      <ErrorScreen onRetry={retry} digest={error.digest} />
    </PageShell>
  );
}

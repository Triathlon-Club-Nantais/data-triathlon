"use client";
import { useEffect } from "react";
import { Button } from "./Button";
import { captureEvent } from "@/lib/posthog";

/**
 * Écran de panne — partagé par `app/error.tsx` et `app/global-error.tsx`.
 *
 * Un seul exemplaire de la microcopie pour les deux frontières d'erreur : elles
 * disent la même chose au visiteur (« la page ne s'est pas affichée »), et deux
 * copies auraient dérivé, ce qui est exactement le défaut `COPY-1` de l'audit.
 * Le composant ne reçoit **jamais** `error.message` : en production Next.js y
 * substitue son paragraphe anglais sur le `digest`, et en développement il peut
 * porter des détails serveur (`ETAT-1`, `COPY-3`).
 *
 * La phrase nomme la cause la plus fréquente — le réveil à froid du backend
 * Render — sans l'affirmer : la frontière attrape aussi les erreurs de rendu
 * client, où « le serveur n'a pas répondu » serait faux. Elle ne renvoie au code
 * d'incident que **s'il existe** : une erreur de rendu client et les builds de
 * développement n'en portent pas, et « signalez-la avec le code ci-dessous »
 * pointerait alors sur rien. Sans code, elle nomme la bulle de signalement, qui
 * est à l'écran dans les deux cas.
 *
 * La mesure PostHog vit ici, et non dans les deux frontières : `global-error`
 * est la panne la plus grave et c'est celle qu'on comptait le moins. Elle est
 * distincte du `capture_exceptions` d'`instrumentation-client.ts` — celui-ci
 * remonte les exceptions, celle-là compte les visiteurs qui *voient* l'écran.
 *
 * La sortie est un `<a>`, pas un `next/link`, et elle ne pointe pas sur
 * `/dashboard`. Deux raisons qui se tiennent ensemble : la frontière ne se vide
 * que si le **chemin change** (`client/components/error-boundary.js`), or
 * `/dashboard` est la page d'accueil (`app/page.tsx` y redirige) et la plus
 * exposée au réveil à froid — un `Link` vers elle depuis sa propre panne ne
 * changerait rien à l'écran. Un chargement complet du document sort de la
 * frontière quelle que soit la page en cause.
 *
 * Le h1 reprend la typographie de `PageHeader` mais pas sa mise en page :
 * l'écran est centré et sans rien d'autre, parce qu'il est un cul-de-sac, là où
 * `PageHeader` titre une page qui a du contenu sous elle (`not-found.tsx`, qui
 * garde une navigation, l'utilise).
 */
export function ErrorScreen({ onRetry, digest }: { onRetry: () => void; digest?: string }) {
  useEffect(() => {
    captureEvent("error_screen_shown", { digest: digest ?? null });
  }, [digest]);

  return (
    <div role="alert" className="mx-auto flex max-w-lg flex-col items-center gap-4 py-16 text-center">
      <h1 className="font-heading text-[28px] leading-none tracking-tight text-foreground sm:text-[40px]">
        Cette page n&apos;a pas pu s&apos;afficher
      </h1>
      <p className="text-sm text-[var(--tcn-text-body)]">
        Le plus souvent, le serveur du club sortait de veille et un nouvel essai suffit. Si
        l&apos;erreur revient, signalez-la
        {digest
          ? " avec le code ci-dessous."
          : " avec la bulle de signalement, en bas de l'écran."}
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button onClick={onRetry}>Réessayer</Button>
        {/* `<a>` volontaire, pas `next/link` : voir l'en-tête du fichier. */}
        <a
          href="/resultats"
          className="inline-flex min-h-[24px] items-center text-sm font-semibold text-foreground underline"
        >
          Voir les résultats
        </a>
      </div>
      {digest && (
        <p className="text-xs text-[var(--tcn-text-muted)]">
          Code de l&apos;incident : <span className="font-mono">{digest}</span>
        </p>
      )}
    </div>
  );
}

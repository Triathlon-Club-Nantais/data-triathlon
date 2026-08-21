"use client";
import Link from "next/link";
import { Button } from "./Button";

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
 * client, où « le serveur n'a pas répondu » serait faux.
 */
export function ErrorScreen({ onRetry, digest }: { onRetry: () => void; digest?: string }) {
  return (
    <div role="alert" className="mx-auto flex max-w-lg flex-col items-center gap-4 py-16 text-center">
      <h1 className="font-heading text-[28px] leading-none tracking-tight text-foreground sm:text-[40px]">
        Cette page n&apos;a pas pu s&apos;afficher
      </h1>
      <p className="text-sm text-[var(--tcn-text-body)]">
        Le plus souvent, le serveur du club sortait de veille et un nouvel essai suffit. Si
        l&apos;erreur revient, signalez-la avec le code ci-dessous.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button onClick={onRetry}>Réessayer</Button>
        <Link
          href="/dashboard"
          className="inline-flex min-h-[24px] items-center text-sm font-semibold text-foreground underline"
        >
          Revenir au tableau de bord
        </Link>
      </div>
      {digest && (
        <p className="text-xs text-[var(--tcn-text-muted)]">
          Code de l&apos;incident : <span className="font-mono">{digest}</span>
        </p>
      )}
    </div>
  );
}

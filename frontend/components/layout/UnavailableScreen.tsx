"use client";
import { useRouter } from "next/navigation";
import { ErrorScreen } from "@/components/tcn/ErrorScreen";
import { PageShell } from "./PageShell";

/**
 * L'écran d'indisponibilité du site (`ErrorScreen`), rendu **en place** par une
 * garde serveur qui n'a pas pu lire la session. « Réessayer » rejoue le rendu
 * serveur (`router.refresh()`), donc refait l'appel qui a échoué : c'est ce qui
 * guérit le réveil à froid du backend, comme `retry()` dans `app/error.tsx`.
 */
export function UnavailableScreen() {
  const router = useRouter();
  return (
    <PageShell>
      <ErrorScreen onRetry={() => router.refresh()} />
    </PageShell>
  );
}

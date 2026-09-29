"use client";
import { useEffect, useSyncExternalStore } from "react";

/**
 * « Le code d'accès a été accepté sur cette page » (#1057), dit par
 * `app/(public_restricted)/layout.tsx` au pied de page du layout racine, qui
 * n'en est pas un descendant : un contexte n'y monterait pas. Un compteur
 * plutôt qu'un booléen, pour qu'une transition entre deux pages du groupe ne
 * fasse pas clignoter le geste.
 */
let marqueurs = 0;
const abonnes = new Set<() => void>();

function prevenir() {
  for (const abonne of abonnes) abonne();
}

function abonner(abonne: () => void) {
  abonnes.add(abonne);
  return () => abonnes.delete(abonne);
}

export function useSiteAccessOpen(): boolean {
  return useSyncExternalStore(abonner, () => marqueurs > 0, () => false);
}

/** Posé par la garde du site **seulement** sur un accès avéré. */
export function SiteAccessOpenMarker() {
  useEffect(() => {
    marqueurs += 1;
    prevenir();
    return () => {
      marqueurs -= 1;
      prevenir();
    };
  }, []);
  return null;
}

"use client";

import { useSyncExternalStore } from "react";

/** Le point de rupture `md` de Tailwind, en requête média. */
const COMPACT = "(max-width: 767px)";

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
  const requete = window.matchMedia(COMPACT);
  requete.addEventListener("change", onChange);
  return () => requete.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
  return window.matchMedia(COMPACT).matches;
}

function getServerSnapshot(): boolean {
  return false;
}

/**
 * `true` sous le point de rupture `md`.
 *
 * `useSyncExternalStore` porte exactement les deux instantanés requis :
 * `false` au rendu serveur — où `matchMedia` n'existe pas, et partir de la
 * vraie valeur produirait une non-concordance d'hydratation — puis la vraie
 * valeur dès l'hydratation, resynchronisée sur l'événement `change` du media
 * query sans état local ni effet (même patron que `useIsSelectedAthlete`,
 * `components/layout/AthletePicker.tsx`).
 */
export function useEstCompact(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

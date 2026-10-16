import { useSyncExternalStore } from "react";

const noSubscription = () => () => {};

/** Faux au rendu serveur **et** au premier rendu client qui l'hydrate, vrai ensuite. */
export function useHydrated(): boolean {
  return useSyncExternalStore(noSubscription, () => true, () => false);
}

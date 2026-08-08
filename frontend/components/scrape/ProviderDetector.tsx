"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { useDebounce } from "@/hooks/useDebounce";
import { Badge } from "@/components/ui/badge";
import { providerLabel } from "@/lib/constants";

type Detected = { provider: string; supported: boolean };

export function ProviderDetector({ url }: { url: string }) {
  const debounced = useDebounce(url, 400);
  const [detected, setDetected] = useState<Detected | null>(null);

  useEffect(() => {
    if (!debounced || !debounced.startsWith("http")) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setDetected(null);
      return;
    }
    let cancelled = false;
    apiClient
      .detectProvider(debounced)
      .then((r) => {
        if (cancelled) return;
        // Le support est tranché par le registre backend, jamais par une liste
        // tenue ici : la précédente avait divergé et affichait « Non supporté »
        // sur Competitor, RaceResult et Chronoplace, pourtant importables.
        setDetected(r);
      })
      .catch(() => !cancelled && setDetected(null));
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  if (!detected) return null;
  const { provider, supported } = detected;
  // Deux états, pas trois : `is_supported` et `detect_provider` sont adossés au
  // même `get_provider(url)` côté registre, donc `supported` ⟺ `provider !== ""`.
  // Nommer un fournisseur non supporté donnerait « Non supporté (Source) », le
  // repli de `providerLabel` — un faux nom pour un état que l'API ne rend pas.
  return supported ? (
    <Badge variant="default">{`Fournisseur : ${providerLabel(provider)}`}</Badge>
  ) : (
    <Badge variant="destructive">Non supporté — saisie manuelle</Badge>
  );
}

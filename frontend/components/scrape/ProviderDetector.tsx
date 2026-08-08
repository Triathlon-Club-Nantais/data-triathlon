"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { useDebounce } from "@/hooks/useDebounce";
import { Badge } from "@/components/ui/badge";
import { providerLabel } from "@/lib/constants";

type Detected = { provider: string; supported: boolean };

export function ProviderDetector({
  url,
  onDetected,
}: {
  url: string;
  onDetected?: (provider: string) => void;
}) {
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
        onDetected?.(r.provider);
      })
      .catch(() => !cancelled && setDetected(null));
    return () => {
      cancelled = true;
    };
  }, [debounced, onDetected]);

  if (!detected) return null;
  const { provider, supported } = detected;
  if (!supported) {
    // `provider` est vide quand aucun chronométreur ne reconnaît l'URL : le
    // nommer donnerait « Non supporté (Source) », le repli de `providerLabel`.
    return (
      <Badge variant="destructive">
        {provider
          ? `Non supporté (${providerLabel(provider)}) — saisie manuelle`
          : "Non supporté — saisie manuelle"}
      </Badge>
    );
  }
  return <Badge variant="default">{`Fournisseur : ${providerLabel(provider)}`}</Badge>;
}

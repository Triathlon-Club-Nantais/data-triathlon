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
        // Le repli couvre un front déployé avant son backend.
        setDetected({
          provider: r.provider,
          supported: r.supported ?? r.provider !== "playwright",
        });
        onDetected?.(r.provider);
      })
      .catch(() => !cancelled && setDetected(null));
    return () => {
      cancelled = true;
    };
  }, [debounced, onDetected]);

  if (!detected) return null;
  const { provider, supported } = detected;
  const label = providerLabel(provider);
  return (
    <Badge variant={supported ? "default" : "destructive"}>
      {supported ? `Fournisseur : ${label}` : `Non supporté (${label}) — saisie manuelle`}
    </Badge>
  );
}

"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { useDebounce } from "@/hooks/useDebounce";
import { Badge } from "@/components/ui/badge";

const SUPPORTED = ["klikego", "breizhchrono", "timepulse", "wiclax", "prolivesport", "sportinnovation"];

export function ProviderDetector({
  url,
  onDetected,
}: {
  url: string;
  onDetected?: (provider: string) => void;
}) {
  const debounced = useDebounce(url, 400);
  const [provider, setProvider] = useState<string | null>(null);

  useEffect(() => {
    if (!debounced || !debounced.startsWith("http")) {
      setProvider(null);
      return;
    }
    let cancelled = false;
    apiClient
      .detectProvider(debounced)
      .then((r) => {
        if (cancelled) return;
        setProvider(r.provider);
        onDetected?.(r.provider);
      })
      .catch(() => !cancelled && setProvider(null));
    return () => {
      cancelled = true;
    };
  }, [debounced, onDetected]);

  if (!provider) return null;
  const supported = SUPPORTED.includes(provider);
  return (
    <Badge variant={supported ? "default" : "destructive"}>
      {supported ? `Fournisseur : ${provider}` : `Non supporté (${provider}) — saisie manuelle`}
    </Badge>
  );
}

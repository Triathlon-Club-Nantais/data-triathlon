"use client";

import { useState } from "react";
import { CSPProvider } from "@base-ui/react/csp-provider";

/**
 * `CSPProvider` figé sur le nonce du premier rendu (#570). `router.refresh()`
 * rejoue le layout racine avec le nonce d'une nouvelle requête, alors que la
 * CSP du document reste celle du chargement initial : un `<style>` de Base UI
 * signé ensuite par ce nonce neuf était rapporté en violation, et serait bloqué.
 */
export function StableCSPProvider({ nonce, children }: { nonce?: string; children: React.ReactNode }) {
  const [documentNonce] = useState(nonce);
  return <CSPProvider nonce={documentNonce}>{children}</CSPProvider>;
}

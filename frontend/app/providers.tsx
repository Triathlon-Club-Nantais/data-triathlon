"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import posthog from "posthog-js";
import { useSession } from "@/lib/queries/auth";

/**
 * Synchronise l'identité PostHog avec la session courante.
 *
 * Doit tourner sous QueryClientProvider pour que useSession (React Query)
 * fonctionne. Le useEffect est justifié ici : identifier un utilisateur pour
 * l'analytics, c'est une synchronisation avec un système externe (PostHog),
 * pas une réaction à une action utilisateur.
 *
 * posthog.reset() se déclenche ici, pas dans le handler de clic « se
 * déconnecter » — cet effet est le seul endroit où « une session identifiée
 * vient de disparaître » est observable quelle qu'en soit la cause
 * (déconnexion explicite, 401, expiration, révocation admin), donc le seul
 * qui les couvre toutes.
 */
function PostHogSessionSync() {
  const { data: session } = useSession();
  // Garde reset() : ne se déclenche que sur une vraie transition
  // connecté → déconnecté, jamais au premier chargement anonyme (session
  // === null sans qu'on ait jamais identifié personne).
  const identifiedRef = useRef(false);

  useEffect(() => {
    if (!process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN) return;
    if (session) {
      identifiedRef.current = true;
      posthog.identify(String(session.id), {
        email: session.email,
        name: session.display_name,
        roles: session.roles.map((r) => r.slug),
      });
    } else if (session === null && identifiedRef.current) {
      identifiedRef.current = false;
      posthog.reset();
    }
  }, [session]);

  return null;
}

// TCN Design System : thème clair uniquement (le mode sombre a été retiré).
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <PostHogSessionSync />
      {children}
    </QueryClientProvider>
  );
}

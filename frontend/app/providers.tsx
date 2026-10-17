"use client";
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { useAnalyticsConsent } from "@/lib/analytics-consent";
import { withPostHog } from "@/lib/posthog";
import { RETOUR_CONNEXION_KEY } from "@/lib/constants";
import { SESSION_QUERY_DEFAULTS, useSession } from "@/lib/queries/auth";
import { queryKeys } from "@/lib/queries/keys";
import { ImportStreamProvider } from "@/components/scrape/ImportStreamProvider";
import { clearAthlete, readAthlete, writeAthlete } from "@/components/layout/AthletePicker";

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
 *
 * L'identification n'a lieu qu'avec l'accord à la mesure détaillée (#1159) :
 * sans lui, la mesure reste anonyme et sans cookie.
 */
function PostHogSessionSync() {
  const { data: session } = useSession();
  const consent = useAnalyticsConsent();
  // Garde reset() : ne se déclenche que sur une vraie transition
  // connecté → déconnecté, jamais au premier chargement anonyme (session
  // === null sans qu'on ait jamais identifié personne).
  const identifiedRef = useRef(false);

  useEffect(() => {
    if (session && consent === "granted") {
      identifiedRef.current = true;
      const properties = {
        email: session.email,
        name: session.display_name,
        roles: session.roles.map((r) => r.slug),
      };
      withPostHog((posthog) => posthog.identify(String(session.id), properties));
    } else if (session === null && identifiedRef.current) {
      identifiedRef.current = false;
      withPostHog((posthog) => posthog.reset());
    }
  }, [session, consent]);

  return null;
}

/**
 * Ramène au point de départ après connexion (#494).
 *
 * Le backend redirige vers le premier espace ouvert, l'accueil `/` pour un
 * compte sans pouvoir (FR-026 : destination fixée par le code, aucun `next` ne
 * circule côté serveur ; #1297, #1322). `UserMenu`
 * mémorise le chemin d'origine dans `sessionStorage` avant de router vers
 * `/login` ; ce composant le relit dès qu'une session existe et, s'il diffère
 * de l'atterrissage, y ramène côté client — sans jamais toucher au serveur ni
 * à l'URL d'`/authorize`.
 *
 * L'atterrissage est figé dans `atterrissageRef` au tout premier effet, jamais
 * relu au chemin courant : entre le retour du fournisseur et la résolution de
 * `useSession` (un aller-retour réseau), rien n'empêche l'utilisateur de
 * naviguer ailleurs de lui-même — comparer au chemin courant à ce moment-là
 * écraserait cette navigation par la destination mémorisée.
 */
function PostLoginReturn() {
  const { data: session } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const atterrissageRef = useRef<string | null>(null);
  const traiteRef = useRef(false);

  useEffect(() => {
    if (atterrissageRef.current === null) {
      atterrissageRef.current = pathname + window.location.search;
    }
  }, [pathname]);

  useEffect(() => {
    if (!session || traiteRef.current || atterrissageRef.current === null) return;
    traiteRef.current = true;
    const cible = sessionStorage.getItem(RETOUR_CONNEXION_KEY);
    if (!cible) return;
    sessionStorage.removeItem(RETOUR_CONNEXION_KEY);
    if (cible !== atterrissageRef.current) {
      router.replace(cible);
      toast.success("Connexion réussie");
    }
  }, [session, router]);

  return null;
}

/**
 * La fiche rattachée au compte (#1325) devient l'athlète retenu du stock local :
 * toutes les surfaces qui lisent `useSelectedAthlete` la suivent sans rien
 * savoir de la session (`docs/frontend/athlete-retenu.md`). Le détachement vide
 * le stock ; une déconnexion le laisse, comme avant.
 */
function SessionAthleteSync() {
  const { data: session } = useSession();

  useEffect(() => {
    const athlete = session?.athlete;
    if (athlete) {
      const retenu = readAthlete();
      if (retenu?.id !== athlete.id || retenu.nom !== athlete.nom || retenu.prenom !== athlete.prenom) {
        writeAthlete({ id: athlete.id, prenom: athlete.prenom, nom: athlete.nom });
      }
      marquer(true);
    } else if (session && marquer()) {
      // Le marqueur vit à côté du stock, pas dans un `ref` : un détachement fait
      // depuis un autre appareil se constate au chargement suivant.
      marquer(false);
      clearAthlete();
    }
  }, [session]);

  return null;
}

const STOCK_DE_SESSION = "tcn-athlete-from-session";

/** Lit, pose ou retire le marqueur « stock écrit par la session ». */
function marquer(valeur?: boolean): boolean {
  try {
    if (valeur === true) window.localStorage.setItem(STOCK_DE_SESSION, "1");
    else if (valeur === false) window.localStorage.removeItem(STOCK_DE_SESSION);
    return window.localStorage.getItem(STOCK_DE_SESSION) === "1";
  } catch {
    return false;
  }
}

// TCN Design System : thème clair uniquement (le mode sombre a été retiré).
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(() => {
    const queryClient: QueryClient = new QueryClient({
      defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
      // Les pastilles du rail tiennent 5 min (#1385) : toute écriture réussie
      // peut changer une file, comme côté serveur où tout commit vide le cache.
      mutationCache: new MutationCache({
        // Sans attendre : la mutation elle-même n'a pas à patienter derrière ce recompte.
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.adminBadgeCounts() });
        },
      }),
    });
    queryClient.setQueryDefaults(queryKeys.session(), SESSION_QUERY_DEFAULTS);
    return queryClient;
  });
  return (
    <QueryClientProvider client={client}>
      <PostHogSessionSync />
      <PostLoginReturn />
      <SessionAthleteSync />
      <ImportStreamProvider>{children}</ImportStreamProvider>
    </QueryClientProvider>
  );
}

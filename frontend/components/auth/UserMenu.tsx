"use client";
import { useEffect, useRef } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { usePathname, useRouter } from "next/navigation";
import { Avatar, Button } from "@/components/tcn";
import { RETOUR_CONNEXION_KEY } from "@/lib/constants";
import { nomComplet } from "@/components/layout/AthletePicker";
import { useLogout, useSession } from "@/lib/queries/auth";
import type { SessionUser } from "@/lib/types";

// Le menu Base UI ne sert qu'à un connecté sur le rail : hors du premier
// chargement de chaque page, où il pesait ~17 Ko gzip (#1603).
const UserMenuDropdown = dynamic(
  () => import("./UserMenuDropdown").then((module) => module.UserMenuDropdown),
  // Repère muet à la taille de l'avatar : ni décalage du rail, ni annonce.
  { loading: () => <div aria-hidden style={{ width: 34, height: 34, flex: "none" }} /> },
);

/**
 * Bouton « Se connecter » si anonyme, menu utilisateur sinon.
 *
 * Posé **deux fois** par `AppNav` — pied du rail et pied du tiroir mobile.
 * Les deux formes ne coexistent jamais à l'écran : le rail est `hidden md:flex`,
 * le tiroir `md:hidden`.
 *
 * `onNavigate` s'appelle au moment où une navigation **a réellement lieu**
 * (#482, NAV-4) : juste avant `router.push("/login")`, ou dans le `onSuccess`
 * de la déconnexion — jamais au clic de « Se déconnecter » lui-même, qui
 * couperait l'affichage de son état d'attente (`logout.isPending`) avant que
 * la requête n'ait eu le temps de partir. Un prop fonction ne pose ici aucun
 * problème de sérialisation Next : `UserMenu` n'est aujourd'hui rendu que par
 * `AppNav`, lui-même `"use client"` — aucune frontière serveur/client n'est
 * traversée à l'un ou l'autre de ses deux points d'appel. Un futur appelant
 * serveur rouvrirait la question.
 */
export function UserMenu({
  pleineLargeur = false,
  onNavigate,
}: {
  pleineLargeur?: boolean;
  onNavigate?: () => void;
}) {
  const { data: session, isPending, errorUpdateCount, refetch, isFetching } = useSession();
  const logout = useLogout();
  const router = useRouter();
  const chemin = usePathname();

  // Le bouton « Réessayer » du tiroir disparaît avec la panne : sans relais, le
  // focus tomberait sur `body` au retour de la session.
  const tiroir = useRef<HTMLDivElement>(null);
  const relance = useRef(false);
  useEffect(() => {
    if (session === undefined || !relance.current) return;
    relance.current = false;
    if (document.activeElement === document.body) tiroir.current?.querySelector<HTMLElement>("a, button")?.focus();
  }, [session]);

  // Une session illisible n'est pas une session anonyme (#954) : proposer
  // « Se connecter » à un connecté relancerait un parcours OAuth inutile.
  // Après un succès, React Query garde `data` et le menu reste affiché.
  // `errorUpdateCount` plutôt que `isError` : sans `data`, une nouvelle
  // tentative repasse la query en `pending`, ce qui démonterait le bouton.
  if (session === undefined && errorUpdateCount > 0) {
    return (
      <div
        role="status"
        style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", width: pleineLargeur ? "100%" : undefined }}
      >
        <span style={{ fontSize: 13, color: "var(--tcn-text-muted)" }}>Session indisponible</span>
        {/* `aria-disabled` plutôt que `disabled`, qui renverrait le focus sur `body`. */}
        <Button
          variant="secondary"
          size="sm"
          aria-disabled={isFetching || undefined}
          onClick={() => {
            if (isFetching) return;
            relance.current = true;
            void refetch();
          }}
        >
          {isFetching ? "Nouvelle tentative…" : "Réessayer"}
        </Button>
      </div>
    );
  }

  // Faire clignoter « Se connecter » avant de le remplacer par un nom est pire
  // que d'attendre : la place du compte est tenue par un repère neutre.
  if (isPending) return <SessionEnLecture />;

  if (!session) {
    // Navigation par le **routeur**, jamais un `<Link>` enveloppant ce bouton :
    // `Button` rend un `<button>`, et un `<a>` autour serait deux éléments
    // interactifs imbriqués — HTML invalide, annoncé deux fois par les
    // technologies d'assistance. C'est déjà la forme des deux autres actions de
    // la topbar (« Ajouter une épreuve »).
    return (
      <Button
        variant="secondary"
        onClick={() => {
          // Mémorisé côté navigateur seulement (#494) : le backend redirige
          // vers le premier espace ouvert (FR-026, #1297, #1322), `PostLoginReturn` (providers.tsx)
          // lit cette clé à l'atterrissage pour ramener au point de départ.
          // `window.location.search` et non `useSearchParams()` : ce dernier
          // impose une frontière Suspense, inutile pour une simple lecture au
          // clic — voir le commentaire équivalent dans `app/login/page.tsx`.
          if (chemin !== "/login") {
            sessionStorage.setItem(RETOUR_CONNEXION_KEY, chemin + window.location.search);
          }
          onNavigate?.();
          router.push("/login");
        }}
        style={{ width: pleineLargeur ? "100%" : undefined }}
      >
        Se connecter
      </Button>
    );
  }

  const nom = session.display_name || session.email;
  const seDeconnecter = () => {
    // posthog.reset() n'est pas appelé ici : PostHogSessionSync (providers.tsx)
    // le déclenche dès que session repasse à null, quelle qu'en soit la cause.
    logout.mutate(undefined, {
      onSuccess: () => {
        router.push("/");
        onNavigate?.();
      },
    });
  };

  // Tiroir mobile : l'état connecté se déplie **à plat**. Un menu déroulant
  // dans un tiroir serait un menu dans un menu, et son popup sortirait du
  // piège de focus du tiroir. Le lien « Administration » a été retiré (revue
  // humaine PR #214) : la catégorie Administration de la nav le rend redondant.
  if (pleineLargeur) {
    return (
      <div ref={tiroir} style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
          <Avatar name={nom} size={34} />
          <Identite session={session} />
        </div>
        <Link href="/mon-compte" className="tcn-btn tcn-btn--md tcn-btn--secondary" onClick={onNavigate}>
          Mon compte
        </Link>
        <Button variant="secondary" disabled={logout.isPending} onClick={seDeconnecter}>
          Se déconnecter
        </Button>
      </div>
    );
  }

  return (
    <UserMenuDropdown
        email={session.email}
        nom={nom}
        deconnexionEnCours={logout.isPending}
        onDeconnexion={seDeconnecter}
      >
        <Identite session={session} />
      </UserMenuDropdown>
  );
}

/** Place du compte tant que la session est en lecture, sans rien affirmer (#954). */
export function SessionEnLecture() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Lecture de la session"
      style={{
        width: 44,
        height: 44,
        flex: "none",
        borderRadius: "var(--tcn-radius-pill)",
        border: "1.5px solid var(--tcn-border)",
      }}
    />
  );
}

/**
 * Nom affiché, adresse, puis appartenances — l'adresse est toujours lisible,
 * sans survol.
 *
 * Les groupes viennent de `GET /auth/me`, qui les rend **à tout connecté** : à
 * quoi j'appartiens ne demande aucun pouvoir, contrairement à voir les
 * appartenances des autres (`/admin/groupes`). Ils sont posés ici, sous
 * l'identité, et nulle part près d'un rôle : un groupe n'accorde rien, et
 * l'écrire à côté des droits le laisserait croire.
 */
function Identite({ session }: { session: SessionUser }) {
  const tronque = {
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  } as const;
  return (
    <div style={{ minWidth: 0 }}>
      {session.display_name && (
        <div style={{ fontSize: 14, fontWeight: 700, color: "var(--tcn-ink)", ...tronque }}>
          {session.display_name}
        </div>
      )}
      <div style={{ fontSize: 13, color: "var(--tcn-text-muted)", ...tronque }}>
        {session.email}
      </div>
      <EtatFiche session={session} />
      {session.groups.length > 0 && (
        <div style={{ fontSize: 12, color: "var(--tcn-text-muted)", marginTop: 4 }}>
          Membre de {session.groups.map((groupe) => groupe.name).join(" · ")}
        </div>
      )}
    </div>
  );
}

/** Fiche rattachée ou demande en cours (#1325), sous l'adresse. */
function EtatFiche({ session }: { session: SessionUser }) {
  const style = { fontSize: 12, color: "var(--tcn-text-muted)", marginTop: 4 } as const;
  if (session.athlete) return <div style={style}>Fiche : {nomComplet(session.athlete)}</div>;
  const demande = session.athlete_claim;
  if (!demande) return null;
  const etat = demande.status === "pending" ? "Demande en attente" : "Demande refusée";
  return <div style={style}>{etat} : {nomComplet(demande.athlete)}</div>;
}

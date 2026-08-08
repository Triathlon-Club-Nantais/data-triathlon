"use client";
import { useRouter } from "next/navigation";
import { Avatar, Button } from "@/components/tcn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout, useSession } from "@/lib/queries/auth";
import type { SessionUser } from "@/lib/types";

/**
 * Bouton « Se connecter » si anonyme, menu utilisateur sinon.
 *
 * Posé **deux fois** par `AppNav` — pied du rail et pied du tiroir mobile.
 * Les deux formes ne coexistent jamais à l'écran : le rail est `hidden md:flex`,
 * le tiroir `md:hidden`.
 *
 * Ne prend **aucun callback** : la fermeture du tiroir mobile se fait par
 * remontée du clic sur le conteneur, dans `AppNav`. Une prop fonction ferait
 * ici l'objet d'un avertissement de sérialisation de Next, ce composant étant
 * un point d'entrée « use client ».
 */
export function UserMenu({ pleineLargeur = false }: { pleineLargeur?: boolean }) {
  const { data: session, isPending } = useSession();
  const logout = useLogout();
  const router = useRouter();

  // Tant que la session n'est pas connue, on n'affiche rien : faire clignoter
  // « Se connecter » avant de le remplacer par un nom est pire que d'attendre.
  if (isPending) return null;

  if (!session) {
    // Navigation par le **routeur**, jamais un `<Link>` enveloppant ce bouton :
    // `Button` rend un `<button>`, et un `<a>` autour serait deux éléments
    // interactifs imbriqués — HTML invalide, annoncé deux fois par les
    // technologies d'assistance. C'est déjà la forme des deux autres actions de
    // la topbar (« Ajouter un triathlon »).
    return (
      <Button
        variant="secondary"
        onClick={() => router.push("/login")}
        style={{ width: pleineLargeur ? "100%" : undefined }}
      >
        Se connecter
      </Button>
    );
  }

  const nom = session.display_name || session.email;
  const seDeconnecter = () =>
    logout.mutate(undefined, { onSuccess: () => router.push("/") });

  // Tiroir mobile : l'état connecté se déplie **à plat**. Un menu déroulant
  // dans un tiroir serait un menu dans un menu, et son popup sortirait du
  // piège de focus du tiroir. Le lien « Administration » a été retiré (revue
  // humaine PR #214) : la catégorie Administration de la nav le rend redondant.
  if (pleineLargeur) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
          <Avatar name={nom} size={34} />
          <Identite session={session} />
        </div>
        <Button variant="secondary" disabled={logout.isPending} onClick={seDeconnecter}>
          Se déconnecter
        </Button>
      </div>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`Compte — ${session.email}`}
        style={{
          display: "inline-flex",
          padding: 0,
          border: "none",
          background: "transparent",
          borderRadius: 999,
          cursor: "pointer",
        }}
      >
        <Avatar name={nom} size={34} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-auto min-w-60 p-1.5">
        <div style={{ padding: "6px 8px 10px", minWidth: 0 }}>
          <Identite session={session} />
        </div>
        <DropdownMenuSeparator />
        {/* Entrée « Administration » retirée (revue humaine PR #214) : la
            catégorie Administration de la nav la porte déjà, et un doublon
            dans le menu compte alourdit l'interface sans rien apporter. */}
        <DropdownMenuItem
          variant="destructive"
          disabled={logout.isPending}
          onClick={seDeconnecter}
          className="px-2 py-2 text-[14px] font-semibold"
        >
          Se déconnecter
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
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
      {session.groups.length > 0 && (
        <div style={{ fontSize: 12, color: "var(--tcn-text-muted)", marginTop: 4 }}>
          Membre de {session.groups.map((groupe) => groupe.name).join(" · ")}
        </div>
      )}
    </div>
  );
}

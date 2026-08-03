"use client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/tcn";
import { useLogout, useSession } from "@/lib/queries/auth";

/**
 * Bouton « Se connecter » si anonyme, menu utilisateur sinon.
 *
 * Posé **deux fois** dans la topbar — bloc desktop et tiroir mobile —, comme
 * toute action de cette barre.
 *
 * Ne prend **aucun callback** : la fermeture du tiroir mobile se fait par
 * remontée du clic sur le conteneur, dans `TcnTopbar`. Une prop fonction ferait
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

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        width: pleineLargeur ? "100%" : undefined,
      }}
    >
      <span
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: "var(--tcn-text-muted)",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          maxWidth: 180,
        }}
        title={session.email}
      >
        {session.display_name || session.email}
      </span>
      <Button
        variant="secondary"
        disabled={logout.isPending}
        onClick={() => logout.mutate(undefined, { onSuccess: () => router.push("/") })}
      >
        Se déconnecter
      </Button>
    </div>
  );
}

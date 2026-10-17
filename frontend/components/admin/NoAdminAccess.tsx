import Link from "next/link";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * Session connectée sans pouvoir d'administration (#1109) : rendu par la garde
 * de `app/admin/layout.tsx` **et** par `AdminIndex`, pour que les deux cas
 * (aucun rôle, ou `pages:preview` seul) disent la même chose. Le callback SSO
 * ne mène plus toujours à `/admin` (#1297) mais peut y mener : sans ce message,
 * la connexion semblait ratée. `space` nomme l'espace refusé.
 */
export function NoAdminAccess({ space = "admin" }: { space?: "admin" | "encadrement" }) {
  return (
    <EmptyState
      title={`Vous êtes connecté, mais aucun écran ${space === "admin" ? "d'administration" : "d'encadrement"} ne vous est ouvert`}
      description="Demandez un rôle à un administrateur du club."
      action={
        // Cible de 44 px sous `md` (patron #953).
        <Link
          href="/dashboard"
          className="tcn-cible-tactile inline-flex items-center text-sm font-semibold text-accent-ink hover:underline"
        >
          Retour au site
        </Link>
      }
    />
  );
}

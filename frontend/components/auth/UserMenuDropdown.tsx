"use client";
import type { ReactNode } from "react";
import { Avatar } from "@/components/tcn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** Menu du compte sur le rail de bureau, chargé à la demande par `UserMenu` (#1603). */
export function UserMenuDropdown({
  email,
  nom,
  deconnexionEnCours,
  onDeconnexion,
  children,
}: {
  email: string;
  nom: string;
  deconnexionEnCours: boolean;
  onDeconnexion: () => void;
  children: ReactNode;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={`Compte — ${email}`}
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
        <div style={{ padding: "6px 8px 10px", minWidth: 0 }}>{children}</div>
        <DropdownMenuSeparator />
        {/* Entrée « Administration » retirée (revue humaine PR #214) : la
            catégorie Administration de la nav la porte déjà, et un doublon
            dans le menu compte alourdit l'interface sans rien apporter. */}
        <DropdownMenuItem
          variant="destructive"
          disabled={deconnexionEnCours}
          onClick={onDeconnexion}
          className="tcn-cible-tactile px-2 py-2 text-[14px] font-semibold"
        >
          Se déconnecter
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { apiClient } from "@/lib/api/client";

/**
 * Retire le cookie d'accès au site de cet appareil (#1057). Le cookie est
 * `httponly` et vit 90 jours : sans ce geste, un poste partagé reste ouvert.
 * « Se déconnecter » (SSO) n'y touche pas, choix consigné dans
 * `backend/app/api/AGENTS.md`.
 */
export function ForgetSiteAccessButton() {
  const router = useRouter();
  const [enCours, setEnCours] = useState(false);

  async function oublier() {
    if (enCours) return;
    setEnCours(true);
    try {
      await apiClient.siteAccessLogout();
      router.replace("/acces");
      router.refresh();
    } catch {
      toast.error("Le code d'accès n'a pas pu être oublié. Réessayez.");
      setEnCours(false);
    }
  }

  return (
    <button
      type="button"
      onClick={oublier}
      aria-busy={enCours}
      // `py-1 -my-1` : cible de 24 px au moins (SC 2.5.8) sans décaler le pied.
      className="-my-1 cursor-pointer py-1 underline underline-offset-2 hover:text-[var(--tcn-ink)]"
      style={{ font: "inherit", color: "inherit", background: "none", border: 0 }}
    >
      Oublier le code d&apos;accès sur cet appareil
    </button>
  );
}

"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { apiClient } from "@/lib/api/client";

/**
 * Retire le cookie d'accès au site de cet appareil (#1057). Le cookie est
 * `httponly` et vit 90 jours : sans ce geste, un poste partagé reste ouvert.
 * « Se déconnecter » (SSO) n'y touche pas, choix consigné dans
 * `backend/app/api/AGENTS.md`. Après l'effacement, la page se rejoue **sur
 * place** : la garde du groupe y rend le formulaire du code sans perdre l'URL
 * (règle de #513), là où une redirection vers `/acces` perdait la destination.
 */
export function ForgetSiteAccessButton() {
  const router = useRouter();
  const [enCours, setEnCours] = useState(false);

  async function oublier() {
    if (enCours) return;
    setEnCours(true);
    try {
      await apiClient.siteAccessLogout();
      router.refresh();
    } catch {
      toast.error("Le code d'accès n'a pas pu être oublié. Réessayez.");
    } finally {
      // Le pied de page survit à la navigation (layout racine) : sans ce
      // réarmement, le geste restait inerte après un premier usage.
      setEnCours(false);
    }
  }

  return (
    <button
      type="button"
      onClick={oublier}
      aria-busy={enCours}
      // Cible de 44 px sous `md` (patron #953), 28 px au-delà.
      className="tcn-cible-tactile inline-flex cursor-pointer items-center underline underline-offset-2 hover:text-[var(--tcn-ink)]"
      style={{ font: "inherit", color: "inherit", background: "none", border: 0 }}
    >
      {enCours ? "Oubli en cours…" : "Oublier le code d'accès sur cet appareil"}
    </button>
  );
}

import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { apiServer } from "@/lib/api/server";

/**
 * Garde d'accès aux écrans d'administration (FR-040).
 *
 * **D'interface seulement** : les ressources d'administration de l'API restent
 * ouvertes, conformément à FR-035 — protéger des routes relève de #115. Cette
 * garde évite d'exposer un écran inutilisable, elle ne protège aucune donnée.
 *
 * Un layout, et non un `middleware.ts` : un middleware ne peut constater que la
 * **présence** du cookie, jamais sa validité — il laisserait passer une session
 * révoquée ou expirée — et son `matcher`, mal borné, intercepterait `/api/*`,
 * cassant la réindirection vers le backend. Un layout couvre en outre les
 * futures sous-routes d'administration sans qu'on y pense.
 *
 * Contrepartie assumée : `/admin`, jusqu'ici prérendue statiquement, devient
 * dynamique. C'est l'effet recherché.
 */
export default async function AdminLayout({ children }: { children: ReactNode }) {
  const session = await apiServer.getSession();
  if (!session) redirect("/login");
  return <>{children}</>;
}

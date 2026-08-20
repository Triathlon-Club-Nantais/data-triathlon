import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { apiServer } from "@/lib/api/server";

/**
 * Garde d'accès au site (#509) — ferme tout ce qui vit sous ce groupe de
 * routes derrière le mot de passe partagé aux adhérents.
 *
 * Un layout, et non `middleware.ts` : même raison que `admin/layout.tsx`
 * (déjà nesté ici) — un middleware ne constate que la présence du cookie,
 * jamais sa validité, et son `matcher` casse facilement les rewrites
 * `/api/*`. Posé sur ce groupe et non sur `app/layout.tsx` : `/acces` et
 * `/benevoles` restent des routes sœurs, jamais soumises à cette garde.
 *
 * Conséquence assumée : toute page de ce groupe devient dynamique — c'est
 * l'effet recherché, au même titre que pour `/admin` avant elle.
 */
export default async function ProtegeLayout({ children }: { children: ReactNode }) {
  const autorise = await apiServer.checkSiteAccess();
  if (!autorise) {
    redirect("/acces");
  }
  return <>{children}</>;
}

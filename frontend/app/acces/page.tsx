import type { Metadata } from "next";
import { SiteAccessGate } from "@/components/site-access/SiteAccessGate";
import { cheminDeRetour } from "@/lib/site-access-return";

export const metadata: Metadata = { title: "Code d'accès" };

/**
 * Route sœur du groupe gardé : c'est la cible d'une navigation directe et le
 * point d'entrée après une déconnexion. Le refus d'accès, lui, rend ce même
 * formulaire **sur place** depuis `app/(public_restricted)/layout.tsx` — d'où `apres`.
 * Un écran d'administration refusé y mène avec `?retour=` (#877) : on y revient
 * ensuite, plutôt qu'à l'accueil.
 */
export default async function AccesPage({
  searchParams,
}: {
  searchParams: Promise<{ retour?: string }>;
}) {
  const { retour } = await searchParams;
  return <SiteAccessGate apres="accueil" retour={cheminDeRetour(retour)} />;
}

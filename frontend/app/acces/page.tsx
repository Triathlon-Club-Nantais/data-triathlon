import { SiteAccessGate } from "@/components/site-access/SiteAccessGate";

/**
 * Route sœur du groupe gardé : c'est la cible d'une navigation directe et le
 * point d'entrée après une déconnexion. Le refus d'accès, lui, rend ce même
 * formulaire **sur place** depuis `app/(public_restricted)/layout.tsx` — d'où `apres`.
 */
export default function AccesPage() {
  return <SiteAccessGate apres="accueil" />;
}

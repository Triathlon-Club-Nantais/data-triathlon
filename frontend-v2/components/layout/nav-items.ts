import {
  LayoutDashboard,
  Trophy,
  Users,
  Map,
  PlusCircle,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/** Entrées de navigation principale (sidebar + drawer mobile). */
export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Tableau de bord", icon: LayoutDashboard },
  { href: "/resultats", label: "Résultats", icon: Trophy },
  { href: "/club", label: "Club", icon: Users },
  { href: "/carte", label: "Carte", icon: Map },
  { href: "/ajouter", label: "Ajouter", icon: PlusCircle },
  { href: "/admin", label: "Admin", icon: ShieldCheck },
];

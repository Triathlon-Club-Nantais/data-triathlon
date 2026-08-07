import type { LucideIcon } from "lucide-react";
import { Briefcase, LayoutGrid, List, Map, UserCog, Users } from "lucide-react";

/**
 * Table de configuration **unique** de la navigation (proto « Navigation TCN »).
 * Ajouter une sous-fonction = une ligne ici, aucun composant à toucher.
 */

/**
 * Échelons d'accès. La production n'en connaît que deux : anonyme, ou connecté.
 * `SessionUser` porte bien `roles`/`permissions` (#115) mais rien ne les
 * attribue encore, et `app/admin/layout.tsx` ne garde `/admin` que sur la
 * **présence** d'une session — la nav s'aligne dessus. `ADMIN` est déclaré,
 * inerte : quand #115 livre l'attribution, on renseigne le rang sans rouvrir un
 * composant.
 */
export const ROLE = { ANON: 0, CONNECTED: 1, ADMIN: 2 } as const;

export type NavItem = {
  id: string;
  label: string;
  /** Absent quand `soon` : l'entrée est portée, pas cliquable. */
  href?: string;
  icon?: LucideIcon;
  minRole?: number;
  /**
   * Code du pouvoir (`core/permissions.py`) sans lequel l'entrée n'est pas
   * portée. **Préférer ceci à `minRole: ROLE.ADMIN`** : `rank` ne vaut jamais
   * `ADMIN`, l'échelon reste inerte, tandis que `session.permissions` est
   * renseigné par `/auth/me` depuis #115.
   *
   * Confort d'affichage seul — n'annoncer que ce qui est faisable. Chaque
   * ressource de l'API porte sa propre garde ; retirer ce champ ouvrirait un
   * menu, jamais une donnée.
   */
  permission?: string;
  /** Écran pas encore livré : porté désactivé plutôt qu'inventé. */
  soon?: boolean;
};

export type NavSection = {
  id: string;
  label: string;
  icon: LucideIcon;
  minRole: number;
  /**
   * Section racine : ses destinations vivent à plat (pas d'intitulé de
   * catégorie, et une tuile par destination en rail compact).
   */
  root?: boolean;
  items: NavItem[];
};

export const NAV: NavSection[] = [
  {
    id: "consulter",
    label: "Consulter",
    icon: LayoutGrid,
    minRole: ROLE.ANON,
    root: true,
    items: [
      { id: "dashboard", label: "Tableau de bord", href: "/dashboard", icon: LayoutGrid },
      { id: "resultats", label: "Résultats", href: "/resultats", icon: List },
      // `MapView.tsx` existe déjà ; l'onglet était masqué (#10, #28) et le reste
      // tant que son rendu sans données n'a pas été vérifié.
      { id: "carte", label: "Carte", icon: Map, soon: true },
    ],
  },
  {
    id: "club",
    label: "Club",
    icon: Users,
    minRole: ROLE.ANON,
    items: [
      // `ClubDashboard.tsx` porte déjà la synthèse **et** les podiums (#128) :
      // une seule destination, pas deux entrées pour un même écran.
      { id: "vueclub", label: "Espace club", soon: true },
      { id: "stats", label: "Statistiques", soon: true },
    ],
  },
  {
    id: "admin",
    label: "Administration",
    icon: Briefcase,
    minRole: ROLE.CONNECTED,
    items: [
      // Aucune entrée ne pointe `/admin` : la racine est le futur tableau de
      // bord global, et un `href` préfixe de tous les autres (`isActive` teste
      // `startsWith`) allumerait cette entrée sur chaque écran d'administration.
      { id: "a-providers", label: "Fournisseurs en attente", href: "/admin/fournisseurs" },
      { id: "a-courses", label: "Gestion des courses", href: "/admin/courses" },
      { id: "a-scrape", label: "Re-scrape à la demande", soon: true },
      { id: "a-quality", label: "Revalidation qualité", soon: true },
      { id: "a-benevolat", label: "Bénévolat", soon: true },
      { id: "a-sessions", label: "Sessions", minRole: ROLE.ADMIN, soon: true },
      { id: "a-flags", label: "Feature flags", minRole: ROLE.ADMIN, soon: true },
    ],
  },
  {
    // Ce qui touche aux **personnes** et à ce qu'elles peuvent faire, en un
    // seul endroit : qui entre (#170), ce que chacun porte et ce que porte un
    // rôle (#115), à quoi l'on appartient (#197). C'était éclaté entre la page
    // `/admin` et une entrée « Utilisateurs & droits » que son échelon rendait
    // invisible.
    //
    // La section entière disparaît pour qui ne porte aucun de ces pouvoirs :
    // `AppNav` retire les sections que le filtrage vide.
    id: "utilisateurs",
    label: "Gestion des utilisateurs",
    icon: UserCog,
    minRole: ROLE.CONNECTED,
    items: [
      {
        id: "u-acces",
        label: "Accès au back-office",
        href: "/admin/acces",
        permission: "allowed_emails:manage",
      },
      // Les trois écrans manquants, leurs API étant livrées : attribuer un rôle
      // (`/admin/users`, #239), composer un rôle (`/admin/roles`, #240), gérer
      // un groupe (`/admin/groups`, #241). Chacun tient en un `href` posé ici
      // et le `soon` retiré.
      { id: "u-roles", label: "Rôles des utilisateurs", permission: "roles:assign", soon: true },
      { id: "u-droits", label: "Droits des rôles", permission: "roles:write", soon: true },
      {
        id: "u-groupes",
        label: "Groupes d'appartenance",
        permission: "groups:assign",
        soon: true,
      },
    ],
  },
];

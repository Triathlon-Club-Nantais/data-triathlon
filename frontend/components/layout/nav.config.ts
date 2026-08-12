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
  /** Absent quand `soon` : rien à atteindre, donc rien à rendre. */
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
  /**
   * Écran pas encore livré : l'entrée reste déclarée ici — cette table **est**
   * la feuille de route de la navigation — mais `AppNav` ne la rend pas (#242).
   * Livrer l'écran tient alors en une ligne : poser le `href`, retirer le
   * `soon`.
   */
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
      //
      // `permission` posé depuis #239 : sans lui, quelqu'un qui vient de se
      // connecter et n'a pas encore de rôle se voyait proposer un lien
      // cliquable dont l'API rend 403. C'est exactement ce que `permission`
      // sert à éviter.
      {
        id: "a-providers",
        label: "Fournisseurs en attente",
        href: "/admin/fournisseurs",
        permission: "pending_providers:read",
      },
      { id: "a-courses", label: "Gestion des courses", href: "/admin/courses" },
      // Pouvoir de lecture de l'écran : `courses:sources` garde les trois
      // routes qu'il consomme (liste, aperçu de fusion, fusion elle-même côté
      // #292) — poser `courses:delete` ici masquerait l'écran à qui peut voir
      // les doublons mais pas fusionner, ce que le composant distingue déjà.
      { id: "a-doublons", label: "Doublons suspects", href: "/admin/doublons", permission: "courses:sources" },
      // Les entrées `soon` ci-dessous n'ont pas de pouvoir nommé : le catalogue
      // n'en porte pas d'évident, et en deviner un serait poser une règle à
      // rectifier le jour où l'écran sort. Sans conséquence — depuis #242 une
      // entrée `soon` n'est plus rendue du tout. La revalidation qualité, elle,
      // a le sien depuis #115.
      // L'écran promis par cette entrée existe depuis #47. `batch:run` et non
      // `batch:read` : `permission` ne porte qu'un code, et c'est le lancement
      // qui donne son nom à l'écran — même arbitrage que `u-roles`.
      {
        id: "a-scrape",
        label: "Re-scrape à la demande",
        href: "/admin/batches",
        permission: "batch:run",
      },
      { id: "a-quality", label: "Revalidation qualité", permission: "quality:override", soon: true },
      { id: "a-benevolat", label: "Bénévolat", soon: true },
      // Pas d'entrée « Sessions » : #169 a livré la révocation **dans**
      // « Accès au back-office » — par adresse ligne à ligne, globale en bas de
      // page. Un second écran pour un unique bouton aurait coûté une entrée de
      // navigation de plus, sur un rail déjà long.
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
      // `roles:assign` seul, alors que l'écran lit aussi `users:read` et
      // `roles:read` : `permission` reste un code unique, faute d'un rôle
      // réaliste qui porterait l'écriture sans les deux lectures. Et l'écran
      // dirait « accès refusé » plutôt que « aucun utilisateur » s'il arrivait.
      {
        id: "u-roles",
        label: "Rôles des utilisateurs",
        href: "/admin/utilisateurs",
        permission: "roles:assign",
      },
      // Composer un rôle (#240). Le pouvoir annoncé est celui d'écriture, mais
      // l'écran ne demande que `roles:read` pour s'afficher : qui porte la
      // lecture sans l'écriture y arrive par l'URL et le trouve en consultation,
      // sans aucun geste offert. La navigation n'est pas une garde.
      {
        id: "u-droits",
        label: "Droits des rôles",
        href: "/admin/droits",
        permission: "roles:write",
      },
      // `groups:assign` plutôt que `groups:read` : l'écran se **consulte** avec
      // la seule lecture, mais annoncer une destination où l'on ne pourrait
      // rien faire n'a pas d'intérêt, et `permission` reste un code unique.
      {
        id: "u-groupes",
        label: "Groupes d'appartenance",
        href: "/admin/groupes",
        permission: "groups:assign",
      },
    ],
  },
];

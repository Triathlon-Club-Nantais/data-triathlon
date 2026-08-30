import type { LucideIcon } from "lucide-react";
import { Briefcase, Gauge, LayoutGrid, List, Map, UserCog, Users } from "lucide-react";

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
  /**
   * Ce que l'entrée annonce — et, pour un écran d'administration, **le titre de
   * la page elle-même** : `ecran()` le rend à son `PageHeader`. Un libellé de
   * rail qui diverge du titre d'arrivée (« Gestion des courses » → « Épreuves »)
   * fait douter d'avoir atterri au bon endroit (ADM-6).
   */
  label: string;
  /**
   * La phrase qui dit **à quoi sert l'écran**, au vouvoiement, telle que son
   * `PageHeader` l'affiche — même source, via `ecran()`. Portée par les entrées
   * d'administration : quatre de leurs libellés sont quasi synonymes pour un
   * bénévole occasionnel, et le sommaire `/admin` les désambiguïse par cette
   * phrase, avant le choix plutôt qu'après (ADM-6).
   */
  description?: string;
  /**
   * Libellé **visible** de la barre basse mobile, quand `label` n'y tient pas
   * (#487 : quatre onglets, ~93 px chacun sur un écran de 375 px). Le nom
   * accessible du lien reste `label` — « Athlètes » ne distingue pas deux
   * écrans à l'oreille. Absent = `label` convient.
   */
  labelCourt?: string;
  /** Absent quand `soon` : rien à atteindre, donc rien à rendre. */
  href?: string;
  icon?: LucideIcon;
  minRole?: number;
  /**
   * Un code, ou plusieurs en **OU** : l'entrée est portée dès que la session en
   * détient un. Le OU sert `/admin/maintenance`, dont les deux purges relèvent
   * de pouvoirs distincts et attribuables séparément (`courses:wipe_all`,
   * `participations:wipe_all`) — n'en nommer qu'un annoncerait l'écran à qui
   * n'y peut rien faire, exactement le défaut que `a-courses` se reproche
   * ci-dessous (ADM-6).
   */
  permission?: string | string[];
  /**
   * Écran pas encore livré : l'entrée reste déclarée ici — cette table **est**
   * la feuille de route de la navigation — mais `AppNav` ne la rend pas (#242).
   * Livrer l'écran tient alors en une ligne : poser le `href`, retirer le
   * `soon`.
   */
  soon?: boolean;
  /**
   * Clé du compteur affiché en badge, résolue par `useNavBadges`
   * (`lib/queries/nav-badges.ts`). Une **clé**, jamais un nombre : cette table
   * est de la configuration, elle ne fait pas de requête.
   *
   * Le badge est masqué à zéro — un « 0 » permanent est du bruit — et la requête
   * n'est émise que si la session porte le `permission` de l'entrée.
   */
  badge?: string;
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
      // `ClubDashboard.tsx` porte la synthèse **et** les podiums (#128) : une
      // entrée pour les deux, pas une par bloc. `Gauge` et non `Trophy` — ce
      // dernier est le glyphe du podium scratch (`lib/podium-scope.tsx`), rendu
      // par `PodiumsList` sur cet écran même.
      { id: "vueclub", label: "Espace club", href: "/club", icon: Gauge },
      { id: "stats", label: "Statistiques", soon: true },
      // Page dédiée, distincte de « Espace club » (#274) : liste nominative
      // par saison, pas une synthèse.
      {
        id: "athletes-saison",
        label: "Athlètes par saison",
        labelCourt: "Athlètes",
        href: "/club/athletes",
        icon: Users,
      },
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
        description:
          "Fournisseurs de chronométrage non pris en charge, signalés automatiquement lors d'un import en échec.",
        href: "/admin/fournisseurs",
        permission: "pending_providers:read",
        badge: "providers",
      },
      // `courses:write` : la correction est le geste courant de l'écran, et
      // c'était la seule entrée de la section sans aucun `permission` — donc la
      // seule proposée à qui n'y peut rien faire (ADM-6). Qui porte
      // `courses:delete` sans l'écriture y arrive par l'URL et trouve la
      // suppression offerte, `CoursesAdminTable` testant les deux séparément :
      // la navigation n'est pas une garde.
      {
        id: "a-courses",
        label: "Épreuves",
        description:
          "Corriger ou retirer une épreuve du catalogue. Ces actions sont irréversibles et tracées.",
        href: "/admin/courses",
        permission: "courses:write",
      },
      // Pouvoir de lecture de l'écran : `courses:sources` garde les trois
      // routes qu'il consomme (liste, aperçu de fusion, fusion elle-même côté
      // #292) — poser `courses:delete` ici masquerait l'écran à qui peut voir
      // les doublons mais pas fusionner, ce que le composant distingue déjà.
      {
        id: "a-doublons",
        label: "Doublons suspects",
        description:
          "Paires d'épreuves qui désignent probablement le même événement — même URL, même identifiant de plateforme, ou noms proches à la même date.",
        href: "/admin/doublons",
        permission: "courses:sources",
        badge: "duplicates",
      },
      // Les entrées `soon` ci-dessous n'ont pas de pouvoir nommé : le catalogue
      // n'en porte pas d'évident, et en deviner un serait poser une règle à
      // rectifier le jour où l'écran sort. Sans conséquence — depuis #242 une
      // entrée `soon` n'est plus rendue du tout.
      // L'écran promis par cette entrée existe depuis #47. `batch:run` et non
      // `batch:read` : `permission` ne porte qu'un code, et c'est le lancement
      // qui donne son nom à l'écran — même arbitrage que `u-roles`.
      {
        id: "a-scrape",
        label: "Batches",
        description:
          "Relancer la récupération des épreuves déjà enregistrées, importer une liste d'épreuves depuis un fichier, et relire le bilan des lancements précédents.",
        href: "/admin/batches",
        permission: "batch:run",
      },
      {
        id: "a-quality",
        label: "Revalidation qualité",
        description:
          "Les épreuves dont l'indice de fiabilité doute. Inspecter, corriger, puis trancher — chaque décision est tracée.",
        href: "/admin/quality",
        permission: "quality:override",
        badge: "quality",
      },
      // Signalement public (#267) — même contraste que « Fournisseurs en
      // attente » : la soumission est ouverte à tous, la consulter exige
      // `feedback:read`.
      {
        id: "a-feedback",
        label: "Retours utilisateurs",
        description:
          "Signalements de bug et retours soumis depuis le bouton du site public.",
        href: "/admin/retours-utilisateurs",
        permission: "feedback:read",
        badge: "feedback",
      },
      // Auto-déclaration self-service depuis `/benevolat` — même contraste que
      // « Retours utilisateurs » : la déclaration est ouverte à tout membre
      // connecté, la consulter/instruire exige `benevolat:read` (#751).
      {
        id: "a-benevolat",
        label: "Déclarations de bénévolat",
        description:
          "Auto-déclarations en attente de validation, et déclarations pour un membre.",
        href: "/admin/benevolat",
        permission: "benevolat:read",
      },
      // Les deux purges globales vivaient en pied de `/admin/courses`, l'écran
      // où l'on vient corriger une date : feuilleter le catalogue jusqu'au bout
      // menait à un clic de la destruction de toute la base (#499, ADM-7). Un
      // écran à elles, et le voisinage disparaît.
      {
        id: "a-maintenance",
        label: "Maintenance",
        description:
          "Les gestes sans retour : vider les résultats, ou vider le catalogue entier. Rien ici ne se répare — chaque geste annonce son ampleur avant d'agir.",
        href: "/admin/maintenance",
        permission: ["participations:wipe_all", "courses:wipe_all"],
      },
      // Lecture du journal existant (#117) — sans elle, la promesse de trace
      // de `DeleteCourseDialog`/`WipeCoursesCard` était invérifiable (#501,
      // ADM-5). Pouvoir dédié : le journal couvre des entités que
      // `courses:delete`/`participations:wipe_all` ne gardent pas.
      // Distincte des Épreuves, et le libellé doit le rester : corriger une
      // épreuve rectifie une ligne, changer cette configuration redéfinit ce
      // que **tous** les compteurs additionnent.
      {
        id: "a-portee-compteurs",
        label: "Portée des compteurs",
        description:
          "Les orthographes sous lesquelles un chronométreur désigne le club, et les disciplines que les compteurs de triathlon laissent de côté.",
        href: "/admin/portee-compteurs",
        permission: "counter_scope:manage",
      },
      {
        id: "a-variantes-club",
        label: "Variantes de club",
        description:
          "Regrouper les orthographes d'un même club — hors TCN, qui garde son propre réglage — sous un nom affiché commun, pour « Top clubs » et le filtre du classement.",
        href: "/admin/variantes-club",
        permission: "club_aliases:manage",
      },
      {
        id: "a-journal",
        label: "Journal d'administration",
        description:
          "L'historique des gestes d'administration sur les données — qui, quoi, quand. Rien ici ne s'annule.",
        href: "/admin/journal",
        permission: "admin_log:read",
      },
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
        description:
          "Seules ces adresses peuvent ouvrir une session. Une adresse retirée perd l'accès immédiatement.",
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
        description:
          "Qui s'est connecté au moins une fois, et ce que chacun porte. Un rôle prend effet à la requête suivante, sans reconnexion.",
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
        description:
          "Un rôle porte des pouvoirs ; les personnes portent des rôles. Une recomposition s'applique dès la requête suivante de chaque porteur, sans reconnexion.",
        href: "/admin/droits",
        permission: "roles:write",
      },
      // `groups:assign` plutôt que `groups:read` : l'écran se **consulte** avec
      // la seule lecture, mais annoncer une destination où l'on ne pourrait
      // rien faire n'a pas d'intérêt, et `permission` reste un code unique.
      {
        id: "u-groupes",
        label: "Groupes d'appartenance",
        description:
          "À quoi chacun appartient — le Codir, les officiels, une section. Un groupe n'accorde aucun droit : ce que l'on peut faire vient des rôles.",
        href: "/admin/groupes",
        permission: "groups:assign",
      },
    ],
  },
];

/**
 * L'en-tête d'un écran — surtitre, titre, phrase — tenu **une fois**, ici, et
 * rendu aux deux endroits qui l'affichent : le `PageHeader` de la page, et la
 * tuile du sommaire `/admin`. Les tenir en double les a déjà fait diverger —
 * le rail annonçait « Gestion des courses » quand l'écran s'intitulait
 * « Épreuves » (ADM-6). Le surtitre suit la **section** pour la même raison :
 * écrit à la main, il annonçait « Maintenance » ou « Exploitation » sur quatre
 * écrans que le sommaire range sous « Administration », donc un changement de
 * lieu apparent en cours de route. Un écran absent de cette table est une
 * erreur de configuration, pas un cas à couvrir en silence.
 */
export function ecran(href: string): {
  eyebrow: string;
  title: string;
  description: string;
} {
  const section = NAV.find((s) => s.items.some((i) => i.href === href));
  const item = section?.items.find((i) => i.href === href);
  if (!section || !item?.description) {
    throw new Error(`Aucune entrée de navigation décrite pour ${href}`);
  }
  return {
    eyebrow: section.label,
    title: item.label,
    description: item.description,
  };
}

/**
 * Une entrée est-elle portée par cette session ? Le rail et le sommaire
 * `/admin` filtrent sur la **même** règle : un écran annoncé à un endroit et tu
 * à l'autre est un écran dont on ne sait plus à qui il s'adresse.
 */
export function estVisible(
  item: NavItem,
  pouvoirs: Set<string>,
  rank: number,
): item is NavItem & { href: string } {
  return (
    !!item.href &&
    !item.soon &&
    rank >= (item.minRole ?? ROLE.ANON) &&
    (!item.permission ||
      (Array.isArray(item.permission)
        ? item.permission.some((code) => pouvoirs.has(code))
        : pouvoirs.has(item.permission)))
  );
}

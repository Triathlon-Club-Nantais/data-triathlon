# Phase 1 — Modèle de données (front)

**Aucune table, aucune migration.** Cette feature ne crée pas de donnée : elle
lit et réécrit celles de #115. Ce document fixe les types TypeScript ajoutés à
`frontend/lib/types.ts`, l'état local de l'écran, et ce qui se **déduit** sans
appel supplémentaire.

## Types transportés

Miroirs exacts des DTO de `backend/app/schemas/admin.py`. Les noms de champs
sont ceux du JSON — ils traversent une frontière, ils ne se traduisent pas.

```ts
/** Un pouvoir de l'inventaire. `code` est technique et stable ; le reste est du français d'affichage. */
export interface Permission {
  code: string;
  label: string;
  description: string;
}

/** Les pouvoirs d'une fonctionnalité, dans l'ordre rendu par le serveur. */
export interface PermissionGroup {
  feature: string;
  permissions: Permission[];
}

/** Un rôle, sa composition et son nombre de porteurs. */
export interface Role {
  id: number;
  organisation_id: number | null;
  slug: string;
  name: string;
  description: string;
  is_system: boolean;
  is_superuser: boolean;
  permissions: string[];
  stale_permissions: string[];
  holders: number;
}

/** Création — `slug` est fixé ici une fois pour toutes. */
export interface RoleCreate {
  slug: string;
  name: string;
  description?: string;
  permissions?: string[];
  is_superuser?: boolean;
}

/** Modification — tout est facultatif, et `permissions` **remplace** l'ensemble. */
export interface RoleUpdate {
  name?: string;
  description?: string;
  permissions?: string[];
  is_superuser?: boolean;
}
```

**`RoleUpdate` ne porte ni `slug`, ni `is_system`, ni `holders`** : le schéma
serveur est `extra="forbid"`, un champ de trop rend **422**. Le type l'interdit
donc à la compilation plutôt qu'à l'exécution.

## Ce qui se déduit, et de quoi

Rien de ce qui suit ne demande d'appel supplémentaire.

| Question de l'écran | Réponse, tirée de |
| --- | --- |
| Ce rôle est-il supprimable ? | `!role.is_system && role.holders === 0` |
| Pourquoi ne l'est-il pas ? | `is_system` → « livré avec l'application » ; sinon le nombre de porteurs |
| Puis-je écrire quoi que ce soit ici ? | `session.permissions.includes("roles:write")` |
| Cette case est-elle basculable ? | `session.permissions.includes(code)` |
| Puis-je basculer le statut de superutilisateur ? | `session.roles.some(r => roles.find(x => x.id === r.id)?.is_superuser)` |
| Ce rôle traîne-t-il des codes périmés ? | `role.stale_permissions.length > 0` |
| Le libellé de ce code porté ? | `inventaire.flatMap(g => g.permissions).find(p => p.code === code)` |

La quatrième ligne est la seule qui croise deux sources — la session et la liste
des rôles. C'est la **même** définition que `authorization._is_superuser` :
« l'un des rôles attribués porte `is_superuser` ». Voir
[research.md](./research.md) §D4 pour ce qui a été écarté.

## État local de l'écran

```ts
// RolePermissionsEditor — l'écran
const [creationOuverte, setCreationOuverte] = useState(false);

// PanneauRole — le brouillon d'un rôle, monté par l'accordéon
const [base, setBase] = useState(role);
const [nom, setNom] = useState(role.name);
const [description, setDescription] = useState(role.description);
const [codes, setCodes] = useState<ReadonlySet<string>>(new Set(role.permissions));
const [purgeDemandee, setPurgeDemandee] = useState(false);
```

**Le brouillon naît à l'ouverture du panneau et meurt à sa fermeture.** Il n'est
jamais fusionné avec la réponse du serveur : après un refus, l'affichage
retombe sur l'état serveur connu, jamais sur ce qu'on a tenté (FR-020).

`base` est cet état serveur **sur lequel le panneau a été ouvert**, et c'est lui,
pas la prop, que le panneau compare et affiche. La prop, elle, continue de vivre :
`roles` se rafraîchit sous un panneau resté ouvert — une création depuis la
même page suffit à l'invalider, et le retour au focus aussi. D'où deux règles qui
n'en font qu'une :

| Ce qu'on lit | Où |
| --- | --- |
| Ce que le brouillon compare, envoie et affiche | `base` |
| Ce que le serveur porte **maintenant** | `role` (la prop) |
| Ce rôle a-t-il bougé sous mes doigts ? | `signature(role) !== signature(base)` |

`signature` exclut `holders` : il change quand le rôle est attribué ailleurs, ce
qui n'entre en conflit avec aucune saisie. Sur conflit, l'écran le dit et
suspend l'enregistrement (FR-020c) — le serveur n'offre ni ETag ni `If-Match`,
donc une écriture concurrente se voit ici ou nulle part.

C'est l'accordéon qui lui donne cette durée de vie, sans qu'aucun état ne la
gouverne : `keepMounted` vaut `false` chez Base UI, donc un panneau fermé est
**démonté** et son `useState` disparaît avec lui. Le `roleOuvert` qu'annonçait
la conception initiale n'existe pas — il aurait dupliqué un état que le
composant tient déjà.

`purgeDemandee` est le quatrième champ, et il n'est pas cosmétique : purger les
codes périmés ne change aucune case, donc rien d'autre ne distinguerait « la
composition est à réécrire » de « rien n'a bougé ».

**La diffusion vers `RoleUpdate` ne retient que ce qui a bougé** :

| Champ envoyé | Condition |
| --- | --- |
| `name` | `brouillon.name !== role.name` |
| `description` | `brouillon.description !== role.description` |
| `permissions` | l'ensemble diffère de `new Set(role.permissions)` |
| `is_superuser` | seulement sur la bascule explicite, jamais dans l'enregistrement de la grille |

C'est cette table qui garantit qu'un renommage ne purge pas les codes périmés
([research.md](./research.md) §D6).

## Invariants portés par le serveur, jamais recalculés ici

L'écran les **anticipe** pour ne pas proposer un geste refusé, mais il ne les
rejoue pas : c'est le serveur qui tranche, et son message qui s'affiche.

| Invariant | Réponse | Anticipé à l'écran par |
| --- | --- | --- |
| Rôle livré, suppression | 409 `SystemRoleError` | bouton désactivé, raison affichée |
| Rôle porté, suppression | 409 `RoleInUseError` (nombre dans le message) | bouton désactivé, nombre affiché |
| Identifiant déjà pris | 409 `SlugTakenError` | rien — la collision se découvre au serveur |
| Pouvoir non détenu, dans un sens ou l'autre | 403 `PrivilegeEscalationError` | case désactivée |
| Statut de superutilisateur posé/retiré sans le porter | 403 | bascule non proposée |
| Dernier administrateur perdu | 409 `LastAdministratorError` | rien — dépend de l'état global |
| Code hors inventaire soumis | 422 `UnknownPermissionError` | inatteignable : les codes viennent de l'inventaire |

Les deux lignes « rien » sont délibérées : ni la collision d'identifiant ni
l'invariant du dernier administrateur ne se calculent depuis l'écran sans
redemander au serveur ce qu'il sait déjà. Leurs messages sont rendus verbatim.

## Codes périmés

`stale_permissions` n'est pas une erreur : ce sont des codes portés en base et
absents de l'inventaire, après un nettoyage de code côté serveur. Ils sont
**inertes** (`effective_permissions` filtre sur `is_known`), **purgeables par
tout le monde** (l'intersection avec l'inventaire les exclut de la
non-amplification) et **jamais bloquants**.

L'écran les affiche sous la grille, dans un bloc distinct qui les nomme comme
tels — code brut, puisqu'aucun libellé n'existe plus pour eux — et annonce que
l'enregistrement de la composition les fera disparaître. C'est la seule voie :
aucune ressource ne les retire seuls.

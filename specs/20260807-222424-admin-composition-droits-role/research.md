# Phase 0 — Décisions

Quinze décisions, chacune avec ce qui a été écarté — dix prises en conception,
cinq nées de la relecture et de la reprise sur `main` (§D11 à §D15). Les faits
sont relevés sur le code livré (#115, #117, #170, #197, #239), pas sur l'énoncé
de #240 : là où les deux divergent, le code tranche (§D1).

---

## D1 — Un rôle `is_system` est modifiable ; seule sa suppression est refusée

**Décision** : l'écran laisse renommer et recomposer un rôle livré avec
l'application. Il n'en désactive que la **suppression**.

**Constaté** :

- `authorization.update_role` ne teste jamais `is_system`, et sa docstring le
  dit : « Un rôle `is_system` est parfaitement modifiable : livré ne veut pas
  dire figé (FR-006). Seule sa suppression est refusée. »
- `authorization.delete_role` lève `SystemRoleError` (409) sur `is_system`.
- La migration `f6a7b8c9d0e1` sème **trois** rôles, tous `is_system=True` :
  `admin` (superutilisateur, aucun pouvoir explicite), `validator`
  (`quality:override`), `moderator` (`pending_providers:{read,handle}`).

**Rationale** : l'énoncé de #240 annonce « un rôle `is_system` est
immodifiable ». Suivi à la lettre, l'écran serait **inopérant au premier jour** :
les trois seuls rôles de l'installation étant livrés, il n'y aurait rien à
composer tant qu'un quatrième n'a pas été créé. La lecture qui rend l'issue
cohérente est celle où « ces gestes » de la phrase suivante désigne les deux
suppressions — celle du rôle livré et celle du rôle porté —, et c'est celle du
code.

**Alternative rejetée** : geler l'édition des rôles `is_system` pour coller à
l'énoncé. Rejetée parce qu'elle interdirait de retirer `quality:override` au
Validateur — un besoin ordinaire — sans autre recours que le SQL, et qu'elle
n'est refusée par aucune ressource : l'écran s'interdirait un geste que le
serveur accepte.

---

## D2 — Un accordéon, un rôle par panneau

**Décision** : la liste des rôles est un `Accordion` (`components/ui/accordion.tsx`,
Base UI). L'en-tête porte le nom, les marqueurs (livré, superutilisateur) et le
nombre de porteurs ; le panneau porte la composition et les gestes.

**Rationale** : c'est la primitive déjà présente qui répond exactement au
besoin — un seul rôle ouvert à la fois, donc une seule grille de dix-huit cases
à l'écran —, et elle est utilisable telle quelle sur mobile sans mise en page
conditionnelle.

**Alternatives rejetées** :

- **Maître-détail deux colonnes** (liste à gauche, composition à droite) :
  demande une mise en page responsive écrite pour cet écran seul, alors que
  l'accordéon la donne. Le dépôt n'a aucun précédent de maître-détail.
- **Une boîte de dialogue de composition par rôle** : dix-huit cases et sept
  intitulés dans une modale, c'est précisément ce que le commit `7c9f563`
  (« rend les modales lisibles sur petit écran ») a dû réparer ailleurs.

---

## D3 — `<fieldset>`/`<legend>` par fonctionnalité, cases à cocher natives

**Décision** : dans le panneau, un `<fieldset>` par fonctionnalité, son
`<legend>` portant l'intitulé rendu par le serveur, et à l'intérieur une
`<input type="checkbox">` native par pouvoir, associée à son `<Label>`, la
description en texte secondaire.

**Rationale** : le regroupement est **sémantique** avant d'être visuel — un
`fieldset` annonce à un lecteur d'écran que les cases qui suivent forment un
ensemble nommé, ce qu'aucune `<div>` stylée ne fait. Les cases natives sont déjà
le patron du dépôt (`SeasonSelector.tsx:79`, `EditCourseDialog.tsx:121`), et
`components/ui/` n'a **ni** `checkbox.tsx` **ni** `switch.tsx`.

**Ordre** : celui du serveur, sans tri ni regroupement côté client.
`grouped_by_feature()` rend l'inventaire « dans l'ordre d'affichage » ; le
re-trier ferait de l'écran un second lieu où cet ordre se décide.

**Alternative rejetée** : ajouter `components/ui/checkbox.tsx` en enveloppant
`@base-ui/react/checkbox`. Une primitive de plus, pour un seul écran, là où la
case native est accessible par construction et déjà employée deux fois.

---

## D4 — Le caractère superutilisateur de l'utilisateur connecté se **déduit**, il ne s'infère pas

**Décision** : l'utilisateur connecté est superutilisateur **si et seulement
si** l'un de ses `session.roles` correspond, par `id`, à un rôle de la liste
chargée portant `is_superuser: true`.

**Constaté** : `GET /auth/me` (`SessionUserRead`) rend `permissions`, `roles` et
`groups` — **pas** `is_superuser`. Côté serveur,
`authorization._is_superuser` répond exactement à cette question : « l'un des
rôles attribués porte-t-il `is_superuser` ». La liste `GET /admin/roles` est
déjà chargée par l'écran, et `SessionRole` porte l'`id`. Le croisement est donc
la **même** définition, pas une approximation.

**Alternative rejetée** : « l'utilisateur porte les dix-huit codes de
l'inventaire, donc il est superutilisateur ». C'est faux dans un sens : un rôle
ordinaire cochant les dix-huit cases produirait la même liste sans franchir les
pouvoirs à venir. L'écran proposerait alors la bascule du statut, et
`assert_may_set_superuser` répondrait 403 — exactement le refus que la spec
demande de ne pas provoquer (SC-003).

**Alternative rejetée** : ajouter `is_superuser` à `SessionUserRead`. Additif
donc licite au regard du Principe IV, mais inutile : la donnée est déjà là.

---

## D5 — Le statut de superutilisateur remplace la grille, il ne la coche pas

**Décision** : quand un rôle porte `is_superuser`, le panneau n'affiche pas la
grille cochée. Il affiche la phrase qui dit ce que le statut fait — franchir
tout pouvoir, **y compris ceux livrés après lui** — et la grille reste visible
en dessous, inerte et signalée comme telle : ces pouvoirs restent la composition
enregistrée du rôle, elle redeviendra effective si le statut est retiré.

**Rationale** : `effective_permissions` court-circuite l'inventaire sur un
superutilisateur (`if _is_superuser: return permissions.CODES`) et
`has_permission` court-circuite **avant même** l'inventaire — c'est la promesse
de FR-014 de #115 : un pouvoir livré demain est franchi demain. Dix-huit cases
cochées diraient « ces dix-huit-là », soit exactement le contresens.

**Bascule** : proposée seulement à qui porte le statut (§D4), et confirmée. Son
retrait peut être refusé par `LastAdministratorError` (409) ; le message du
serveur est rendu tel quel.

---

## D6 — `PATCH` n'envoie que les champs modifiés

**Décision** : la mutation d'édition prend un objet partiel. `permissions` n'est
envoyé **que** si la composition a changé ; `name` et `description` que s'ils
ont changé ; `is_superuser` que s'il bascule.

**Rationale** : `permissions` **remplace** l'ensemble (docstring de
`update_role`, et `RoleUpdate.permissions` est `list[str] | None`). L'envoyer
systématiquement ferait de tout renommage une **purge silencieuse** des codes
périmés du rôle — la spec l'interdit (FR-007, FR-011), et rien à l'écran ne
l'aurait annoncé.

Corollaire : la purge des codes périmés est un geste **volontaire**. Elle
survient lorsque la composition est enregistrée, et l'écran prévient avant la
validation que les codes périmés du rôle disparaîtront par ce geste — c'est la
seule voie, il n'existe aucune ressource pour les retirer seuls.

**Alternative rejetée** : envoyer systématiquement l'état complet du
formulaire. Plus simple à écrire, et faux : `extra="forbid"` sur `RoleUpdate`
rendrait en outre **422** au premier champ de trop (`slug`, `holders`,
`is_system` sont tous dans `RoleRead` et aucun n'est acceptable en `PATCH`).

---

## D7 — La non-amplification fige la case, elle ne la masque pas

**Décision** : une case dont le code n'est pas dans `session.permissions` est
**désactivée dans son état courant**, avec la raison énoncée. Les codes périmés,
eux, restent retirables par tout le monde.

**Constaté** : `assert_may_grant` intersecte avec l'inventaire
(`vises = codes & permissions.CODES`) puis exige que la **différence symétrique**
avant/après soit couverte par les pouvoirs effectifs de l'auteur. Donc : ni
cocher ni décocher un pouvoir non détenu ; et un code périmé, absent de
l'inventaire, n'est jamais visé — sa purge est ouverte à quiconque peut
composer. La docstring le nomme « la condition de réversibilité ».

**Alternative rejetée** : masquer les pouvoirs non détenus. L'écran mentirait
sur la composition du rôle — un Modérateur consulté par quelqu'un qui n'a pas
`pending_providers:handle` paraîtrait ne rien porter.

**Alternative rejetée** : tout laisser cochable et afficher le 403. C'est
exactement ce que l'issue proscrit (« désactiver ces gestes, pas les proposer
pour recueillir un 409 »).

---

## D8 — La création : une boîte de dialogue, et la **même** grille

**Décision** : `CreateRoleDialog` monte le composant `PermissionGrid` utilisé
par l'édition. L'identifiant technique est proposé à partir du nom saisi
(minuscules, accents retirés, espaces en tirets) et reste corrigeable tant qu'il
n'est pas enregistré.

**Constaté** : `RoleCreate` exige `slug` au motif `^[a-z][a-z0-9-]*$`, `name`
non vide, et accepte `permissions` et `is_superuser`. Le slug est **fixé une
fois pour toutes** — `RoleUpdate` l'interdit par `extra="forbid"` (422), parce
qu'il traverse `grant-role --role` et le semis.

**Rationale** : la grille est identique des deux côtés ; l'écrire deux fois
ferait diverger le regroupement, qui est le cœur de la feature.

**Alternative rejetée** : créer un rôle vide puis le composer dans l'accordéon.
Un aller-retour de plus pour le cas nominal, et un rôle sans pouvoir existe
alors en base entre les deux gestes.

**Alternative rejetée** : dériver le slug sans le montrer. Il est immuable et
visible ailleurs (CLI, semis) : le laisser se fabriquer en silence, c'est le
découvrir quand il est trop tard pour le corriger.

---

## D9 — Un troisième `messageDErreur` local, et pas de fabrique

**Décision** : le composant porte sa propre fonction `messageDErreur`, sur le
patron de `AllowedEmailsTable.tsx` et `PendingProvidersTable.tsx`.

**Rationale** : les trois messages ne partagent que la structure `401 / 403 /
autre`. Leur contenu est ce qui compte, et il diffère à chaque fois : « pour
consulter les accès », « votre rôle ne permet pas de gérer les accès au
back-office », et ici « de composer les rôles ». Une fabrique paramétrée
prendrait trois chaînes en argument pour en produire trois — « trois lignes
similaires valent mieux qu'une abstraction prématurée » (Principe VI).

**Précision propre à cet écran** : deux pouvoirs distincts sont en jeu. Un 403
sur la **lecture** signale l'absence de `roles:read` ; l'écran le dit sans nommer
le code, en français, et n'affiche jamais une liste vide à la place.

---

## D10 — Route, cache et navigation

**Décision** :

- Route `/admin/droits`, sous le layout `app/admin/layout.tsx` existant — qui
  couvre déjà les sous-routes et referme sur une session sans aucun pouvoir.
  Nommage français, comme `/admin/acces`, `/admin/courses`, `/admin/fournisseurs`.
- Une clé neuve : `adminPermissions()` → `["admin-permissions"]` (inventaire,
  `staleTime: Infinity` — il est servi depuis le code Python, il ne change qu'au
  déploiement). Pour la liste des rôles, **aucune clé n'est ajoutée** : #239 a
  posé `roles()` → `["roles"]` et son hook `useRoles()`, avec le même
  `retry: false`, pour le même `GET /admin/roles`. Voir §D15.
- Les trois mutations invalident `["roles"]`, `["session"]` et
  `["admin-users"]`. La session, parce que recomposer un rôle qu'on porte
  soi-même est le cas nominal, pas un cas limite : ses pouvoirs effectifs
  changent sous ses pieds. Les utilisateurs, parce que `UserRolesTable` affiche
  le **nom** des rôles attribués — symétrique exact de ce que `useGrantRole`
  fait déjà sur `roles()` pour le compte de porteurs.
- `nav.config.ts` : `u-droits` reçoit `href: "/admin/droits"` et perd `soon`.
  Son `permission: "roles:write"` ne bouge pas.
- La sélection du rôle ouvert vit en `useState`, pas dans l'URL. L'écran n'a ni
  pagination ni filtre à conserver, et personne n'envoie « regarde ce rôle » par
  lien dans un club d'un ou deux administrateurs. Le jour où c'est faux, le
  patron existe (`lib/scope.SCOPE_PARAM`).

**Note assumée** : l'entrée de navigation est portée par `roles:write` alors que
l'écran a besoin de `roles:read` pour afficher quoi que ce soit. Changer la garde
de la navigation serait décider pour #239, qui porte la même paire.

Ce que cette note affirmait initialement — « l'écran y répond par son message
d'accès refusé » — était **faux**, et c'est la revue de code qui l'a relevé : avec
`roles:read` seul, les deux lectures répondent 200 et l'écran s'affiche
entièrement. Voir D12.

## Décisions issues de la revue de code

Quatre défauts trouvés en relecture, dont trois que les tests de la livraison ne
voyaient pas. Ils sont consignés ici parce qu'ils **corrigent** une décision
antérieure, pas parce qu'ils la complètent.

### D11 — La non-amplification vaut aussi dans la modale de création

`authorization.create_role` passe à `assert_may_grant` l'**ensemble complet** des
codes demandés (`authorization.py`), là où `update_role` ne lui passe que la
différence symétrique. La création est donc le chemin le **plus** contraint, et
c'était le seul où la grille était montée sans `disabledCodes` — un 403 garanti
après avoir composé tout le rôle, soit exactement l'anti-patron que D7 rejette.

Conséquence de conception : `figes` ne se calcule plus dans le panneau mais une
fois pour l'écran — il ne dépend ni du rôle ouvert ni du panneau, seulement de la
session et de l'inventaire — et il alimente les deux grilles.

### D12 — `roles:read` sans `roles:write` rend l'écran en consultation

Les deux pouvoirs sont distincts et attribuables séparément : les lectures de
l'écran exigent le premier, ses quatre écritures le second. Le rail de navigation
filtre déjà sur `roles:write`, mais il n'est pas une garde — l'URL reste
atteignable, et `app/admin/layout.tsx` ne referme que sur une session sans aucun
pouvoir. Sans `peutEcrire`, un porteur de `roles:read` obtenait un éditeur
d'apparence complète dont chaque geste finissait en 403.

### D13 — Le brouillon se compare à l'état sur lequel il a été ouvert

Écarté : comparer à la prop. `roles` se rafraîchit sous un panneau resté
ouvert, et alors l'ensemble figé à l'ouverture repart au serveur — où
`permissions` **remplace** — effaçant sans un mot ce qu'un autre administrateur
vient d'ajouter. Écarté aussi : rebaser le brouillon en silence, qui déplace la
perte de la donnée d'autrui vers la saisie en cours.

Retenu : un instantané `base`, un rapprochement de signatures, et sur divergence
un encadré qui le dit et suspend l'enregistrement. Le serveur n'offrant ni ETag
ni `If-Match`, c'est le seul endroit où une écriture concurrente peut se voir.

Le même instantané règle un second défaut sans code supplémentaire : l'encadré
des codes périmés cessait d'être vrai entre la réponse d'une purge et
l'atterrissage du refetch.

### D14 — Ce que le serveur refuserait pour sa forme ne lui est pas soumis

`RoleCreate.slug` porte `pattern=r"^[a-z][a-z0-9-]*$"` et `RoleUpdate.name`
porte `min_length=1`. Sans garde locale, ces deux refus reviennent en message de
validation Pydantic — `String should match pattern '^[a-z][a-z0-9-]*$'` — soit
de l'anglais technique dans une interface française, sur une contrainte que
l'écran connaît d'avance. La forme attendue est donc annoncée en français à côté
du champ. C'est la **seule** duplication de règle serveur assumée ici : elle
porte sur une forme figée dans un schéma, pas sur une décision d'autorisation.

Corollaire : `RoleUpdate` n'a pas `str_strip_whitespace`, donc « Validateur   »
s'enregistrerait tel quel. Le nom est coupé avant comparaison **et** avant envoi.

### D15 — Une seule clé de cache pour `GET /admin/roles`

Découvert à la reprise sur `main` : #239 avait atterri entre-temps et posé
`queryKeys.roles()` avec `useRoles()`, pour la **même** ressource, avec le même
`retry: false` et pour la même raison. La livraison portait `adminRoles()` →
`["admin-roles"]`.

Écarté : garder les deux. Elles auraient tenu deux caches de la même liste, et
aucune des invalidations d'un écran n'aurait touché celle de l'autre — l'écran
d'attribution aurait affiché un `holders` ou un nom de rôle que la composition
venait de changer, et réciproquement.

Retenu : adopter `roles()`. #239 l'avait d'ailleurs anticipé, en toutes lettres —
« les deux écritures invalident **aussi** `roles()` : `RoleRead.holders` compte
les porteurs, et l'écran voisin (#240) l'affiche ». La réciproque manquait : les
trois gestes de composition invalident maintenant `adminUsers()`, parce que
`UserRolesTable` affiche le nom des rôles attribués.

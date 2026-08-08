# Feature Specification: Écran de composition des droits d'un rôle

**Feature Branch**: `admin-cran-de-composition-des-droits-dun-r-le`

**Created**: 2026-08-07

**Status**: Draft

**Input**: issue #240 — deuxième des trois écrans manquants de la section
« Gestion des utilisateurs » (#170), les API étant livrées par #115.

## Contexte

Composer un rôle, c'est choisir les pouvoirs qu'il porte. Aujourd'hui ce geste
n'existe qu'en base : trois rôles sont livrés par la migration initiale
(« Administrateur », « Validateur », « Modérateur »), et rien ne permet d'en
créer un quatrième ni de recomposer les trois autrement qu'en SQL.

C'est le plus dense des trois écrans manquants, et le seul où l'ergonomie fait
une vraie différence : cocher dans une liste plate de dix-huit codes techniques
(`participations:delete`…) est précisément le geste qu'on veut éviter.
L'inventaire des pouvoirs est **déjà regroupé par fonctionnalité** côté serveur,
avec un libellé et une description en français par pouvoir ; l'écran s'appuie
dessus.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lire la composition des rôles (Priority: P1)

Une personne qui administre les droits ouvre l'écran et voit les rôles de
l'installation. Pour chacun : son nom, sa description, le nombre de personnes
qui le portent, et ce qu'il permet de faire — exprimé en français, rangé par
fonctionnalité, jamais sous la forme du seul code technique.

**Why this priority**: c'est la moitié du besoin à elle seule. Aujourd'hui,
répondre à « que peut faire un Modérateur ? » demande d'ouvrir la base. Livré
seul, cet écran supprime déjà ce détour, et il est le socle sur lequel les deux
autres histoires se posent.

**Independent Test**: ouvrir l'écran avec un compte qui peut consulter les
rôles, et vérifier que les trois rôles livrés apparaissent avec leur
composition lisible, sans passer par la base.

**Acceptance Scenarios**:

1. **Given** une installation avec ses trois rôles livrés, **When** j'ouvre
   l'écran, **Then** je vois les trois, chacun avec son nom, sa description et
   le nombre de ses porteurs.
2. **Given** un rôle qui porte « Instruire les signalements », **When** je
   consulte sa composition, **Then** je lis le libellé et la description en
   français, sous l'intitulé de fonctionnalité « Chronométreurs signalés ».
3. **Given** le rôle « Administrateur », **When** je le consulte, **Then** son
   statut de superutilisateur est annoncé comme tel — « franchit tout pouvoir,
   y compris ceux livrés après lui » — et non comme un ensemble de cases
   cochées.
4. **Given** un rôle qui porte en base un code que l'application ne connaît
   plus, **When** je le consulte, **Then** ce code apparaît **distinctement**
   des pouvoirs de l'inventaire, présenté comme périmé et sans effet.
5. **Given** un compte connecté qui ne peut pas consulter les rôles, **When**
   j'ouvre l'écran, **Then** je lis un message d'accès refusé, jamais une liste
   vide.

---

### User Story 2 - Recomposer un rôle existant (Priority: P2)

La même personne modifie un rôle : elle le renomme, corrige sa description, et
coche ou décoche les pouvoirs qu'il porte. Elle enregistre, et le changement
s'applique dès la requête suivante de chaque porteur, sans reconnexion.

**Why this priority**: c'est le geste central de l'écran, mais il suppose la
lecture (US1) pour être seulement compréhensible.

**Independent Test**: retirer un pouvoir au rôle « Validateur », recharger, et
constater que la composition affichée a changé.

**Acceptance Scenarios**:

1. **Given** un rôle existant, **When** je coche un pouvoir supplémentaire et
   j'enregistre, **Then** la composition affichée intègre ce pouvoir et une
   confirmation le dit.
2. **Given** un rôle livré avec l'application, **When** je le consulte, **Then**
   je peux le renommer et recomposer ses pouvoirs — seule sa **suppression**
   lui est refusée.
3. **Given** un pouvoir que je ne porte pas moi-même, **When** je compose un
   rôle, **Then** ce pouvoir m'est présenté dans son état courant sans que je
   puisse le cocher ni le décocher, avec la raison énoncée.
4. **Given** un rôle qui traîne un code périmé, **When** j'enregistre une
   recomposition, **Then** l'écran m'a prévenu que ce code disparaît par le
   même geste, et il disparaît.
5. **Given** que je ne suis pas superutilisateur, **When** je compose un rôle,
   **Then** le statut de superutilisateur ne m'est pas proposé à la bascule.
6. **Given** un enregistrement refusé par le serveur, **When** le refus revient,
   **Then** son message est rendu tel quel et la composition affichée reste
   celle du serveur, jamais celle que j'ai tentée.

---

### User Story 3 - Créer et supprimer un rôle (Priority: P3)

La même personne crée un rôle — un nom, une description, un identifiant stable,
une composition initiale — et supprime celui qui ne sert plus.

**Why this priority**: sans elle l'écran reste utile (recomposer les trois rôles
livrés couvre la plupart des besoins d'un club), mais le besoin « un rôle pour
les bénévoles » n'a pas de réponse.

**Independent Test**: créer un rôle avec un seul pouvoir, le voir apparaître
dans la liste, puis le supprimer et le voir disparaître.

**Acceptance Scenarios**:

1. **Given** l'écran ouvert, **When** je crée un rôle nommé « Bénévole » avec
   un pouvoir coché, **Then** il apparaît dans la liste avec zéro porteur.
2. **Given** un identifiant déjà pris, **When** je valide la création,
   **Then** le refus est énoncé sur le champ concerné, et ma saisie est
   conservée.
3. **Given** un rôle porté par au moins une personne, **When** je le consulte,
   **Then** la suppression ne m'est pas offerte, et la raison est lisible — le
   nombre de porteurs.
4. **Given** un rôle livré avec l'application, **When** je le consulte,
   **Then** la suppression ne m'est pas offerte.
5. **Given** un rôle sans porteur et non livré, **When** je le supprime après
   confirmation, **Then** il disparaît de la liste.

---

### Edge Cases

- **Le dernier administrateur** : décocher le statut de superutilisateur du seul
  rôle qui le porte, ou supprimer ce rôle, laisserait l'installation sans
  personne pour tout franchir. Le serveur refuse ; l'écran rend ce refus tel
  quel plutôt que d'en inventer un second, et l'état affiché reste celui du
  serveur.
- **Identifiant immuable** : l'identifiant technique d'un rôle est fixé à la
  création et ne se modifie plus. L'écran ne le propose pas en modification.
- **Renommer n'est pas recomposer** : corriger un nom ne doit pas emporter les
  pouvoirs, ni purger les codes périmés à l'insu de la personne.
- **Aucun rôle supprimable** : sur une installation neuve, les trois rôles sont
  livrés et donc indélébiles. L'écran n'affiche pas pour autant un état d'erreur.
- **Session expirée** en cours d'édition : message distinct de l'accès refusé.
- **Deux onglets ouverts** : un enregistrement fondé sur une composition périmée
  écrase l'autre. Accepté — un club a un ou deux administrateurs, et le
  verrouillage optimiste n'a pas de support côté API.

## Requirements *(mandatory)*

### Functional Requirements

**Lecture**

- **FR-001**: L'écran DOIT présenter les rôles de l'installation avec, pour
  chacun, son nom, sa description et son nombre de porteurs.
- **FR-002**: Les pouvoirs DOIVENT être présentés **groupés par fonctionnalité**,
  dans l'ordre rendu par le serveur, sans ré-aplatissement ni regroupement
  maison.
- **FR-003**: Chaque pouvoir DOIT être présenté par son libellé et sa
  description en français ; le code technique seul ne suffit jamais.
- **FR-004**: Les codes périmés d'un rôle DOIVENT être visibles et **distincts**
  des pouvoirs de l'inventaire, annoncés comme sans effet.
- **FR-005**: Le statut de superutilisateur DOIT se lire comme un statut — il
  franchit tout pouvoir présent et à venir — et non comme une case parmi les
  autres. Un rôle qui le porte n'affiche pas dix-huit cases cochées.

**Écriture**

- **FR-006**: Une personne habilitée DOIT pouvoir créer un rôle en fournissant
  un nom, un identifiant stable, une description facultative et une composition
  initiale.
- **FR-007**: Elle DOIT pouvoir renommer un rôle et corriger sa description sans
  toucher à sa composition.
- **FR-008**: Elle DOIT pouvoir cocher et décocher les pouvoirs d'un rôle, et
  l'enregistrement DOIT remplacer l'ensemble de la composition.
- **FR-009**: Elle DOIT pouvoir supprimer un rôle qui n'est ni livré avec
  l'application ni porté par quiconque, après confirmation explicite.
- **FR-010**: L'identifiant technique d'un rôle NE DOIT PAS être modifiable
  après sa création.
- **FR-011**: L'enregistrement d'une recomposition emportant des codes périmés
  DOIT l'annoncer avant que la personne ne valide.

**Gestes refusés, désactivés plutôt que proposés**

- **FR-012**: La suppression NE DOIT PAS être offerte sur un rôle livré avec
  l'application, ni sur un rôle porté par au moins une personne ; dans les deux
  cas la raison DOIT être lisible.
- **FR-013**: Un rôle livré avec l'application DOIT rester renommable et
  recomposable — seule sa suppression est refusée par le serveur.
- **FR-014**: Un pouvoir que la personne connectée ne porte pas elle-même NE
  DOIT PAS être basculable par elle, dans un sens comme dans l'autre ; il
  s'affiche dans son état courant, avec la raison. Cela vaut **partout où une
  composition se saisit**, y compris à la création : le serveur y soumet
  l'ensemble complet des codes à la non-amplification, là où une modification ne
  lui soumet que la différence.
- **FR-014b**: L'écran DOIT être en consultation pour qui porte le pouvoir de
  lecture des rôles sans celui de composition : aucun geste d'écriture n'y est
  offert. Les deux pouvoirs sont distincts et attribuables séparément, et l'URL
  reste atteignable même quand la navigation n'y mène pas.
- **FR-015**: La bascule du statut de superutilisateur NE DOIT être offerte
  qu'à une personne qui le porte elle-même.
- **FR-016**: Les codes périmés DOIVENT rester retirables par toute personne
  habilitée à composer, y compris celle qui ne porte pas tous les pouvoirs.

**Refus et erreurs**

- **FR-017**: Un accès refusé DOIT afficher un message d'accès refusé nommant le
  pouvoir manquant en français, jamais une liste vide.
- **FR-018**: Une session expirée DOIT afficher un message distinct de l'accès
  refusé, invitant à se reconnecter.
- **FR-019**: Un refus du serveur (identifiant déjà pris, dernier
  administrateur, rôle encore porté, amplification de privilège) DOIT être rendu
  avec le message du serveur, sans en fabriquer un second.
- **FR-020**: Après un refus, l'état affiché DOIT rester celui du serveur.
- **FR-020b**: Une saisie que le serveur refuserait pour sa **forme** (nom vide,
  identifiant hors de la forme attendue) NE DOIT PAS lui être soumise : la
  contrainte est annoncée en français à côté du champ. Sans cela, le refus
  revient en message de validation anglais.
- **FR-020c**: Si le rôle en cours d'édition change côté serveur pendant la
  saisie, l'écran DOIT le signaler et suspendre l'enregistrement plutôt que
  d'écraser cette modification. La composition remplace l'ensemble et le serveur
  n'offre aucun jeton de version : c'est le seul endroit où une écriture
  concurrente peut se voir.
- **FR-020d**: L'état des droits de la personne connectée DOIT être distingué de
  l'absence de droits : si la session n'a pas pu être lue, l'écran le dit au lieu
  de figer les pouvoirs en affirmant qu'elle n'en porte aucun.

**Navigation**

- **FR-021**: L'entrée de navigation « Droits des rôles » DOIT mener à cet
  écran, et cesser d'être annoncée comme à venir. Elle reste portée par le
  pouvoir de composition des rôles.

### Key Entities

- **Rôle** : un nom d'affichage, une description, un identifiant technique
  stable, un caractère « livré avec l'application », un statut de
  superutilisateur, l'ensemble des pouvoirs qu'il porte, les codes périmés
  qu'il traîne, et le nombre de personnes qui le portent.
- **Pouvoir** : un code technique stable, un libellé et une description en
  français, et la fonctionnalité à laquelle il se rattache.
- **Fonctionnalité** : un intitulé français regroupant les pouvoirs qui s'y
  rapportent, et l'unité d'affichage de l'inventaire — sept aujourd'hui :
  « Rôles et accès », « Groupes d'appartenance », « Chronométreurs signalés »,
  « Qualité des données », « Épreuves », « Coureurs », « Résultats ».
- **Code périmé** : un code porté en base et absent de l'inventaire. Inerte,
  purgeable, jamais bloquant.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Répondre à « que peut faire ce rôle ? » ne demande plus aucun
  accès à la base de données.
- **SC-002**: Composer un rôle de cinq pouvoirs se fait en moins de deux minutes
  sans consulter de documentation, et sans lire un seul code technique.
- **SC-003**: Aucun geste proposé par l'écran ne se solde par un refus du
  serveur pour cause de rôle livré, de rôle porté, ou de pouvoir non détenu :
  ces gestes sont désactivés en amont, avec leur raison affichée.
- **SC-004**: Un accès refusé ne produit jamais d'écran laissant croire qu'aucun
  rôle n'existe.
- **SC-005**: Le regroupement par fonctionnalité affiché est identique, en
  contenu et en ordre, à celui rendu par le serveur ; l'ajout d'un pouvoir côté
  serveur apparaît sans toucher à l'écran.
- **SC-006**: Un changement de composition est effectif pour ses porteurs dès
  leur requête suivante, sans reconnexion.

## Assumptions

- **Divergence assumée avec l'énoncé de #240** : l'issue annonce qu'« un rôle
  `is_system` est immodifiable ». Le code livré par #115 dit l'inverse et le dit
  explicitement — « livré ne veut pas dire figé » (FR-006 de #115) : seule la
  **suppression** d'un rôle livré est refusée, sa modification ne l'est pas.
  Les trois rôles de l'installation étant tous livrés avec elle, geler leur
  modification rendrait l'écran inopérant au premier jour. La spec suit le code.
- **Non-amplification côté interface** : la règle serveur est bornée à la
  différence entre l'avant et l'après, dans les deux sens. Un pouvoir non détenu
  est donc figé dans son état courant plutôt que masqué : le masquer mentirait
  sur la composition du rôle. Les pouvoirs détenus par la personne connectée
  sont connus sans appel supplémentaire — la session les porte déjà.
- **Périmètre** : l'attribution d'un rôle à une personne (#239) et les groupes
  d'appartenance (#241) ne sont pas de cet écran. Le nombre de porteurs s'y
  affiche, la liste nominative des porteurs non.
- **Aucune écriture côté serveur** : les six ressources nécessaires sont livrées
  par #115 et ne sont pas modifiées.
- **Organisation** : l'installation n'a qu'un club. Les rôles livrés sont
  globaux, et l'écran ne présente pas de sélecteur d'organisation.
- **Identifiant technique** : proposé à la création à partir du nom saisi et
  corrigeable tant qu'il n'est pas enregistré, il respecte la forme attendue par
  le serveur.
- **Route** : l'écran vit sous `/admin/droits`, sur le patron français des
  routes d'administration existantes (`/admin/acces`, `/admin/courses`,
  `/admin/fournisseurs`).
- **Pas de verrouillage optimiste** : l'API n'expose pas de jeton de version, et
  le nombre d'administrateurs d'un club ne justifie pas d'en inventer un.

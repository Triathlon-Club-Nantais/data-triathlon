# Feature Specification: Actions d'administration sur la page d'un coureur

**Feature Branch**: `feat/439-athlete-admin-actions`

**Created**: 2026-08-20

**Status**: Draft

**Input**: Issue #439 — « Sur la page d'un athlète avec les pouvoirs nécessaires, je dois pouvoir faire plusieurs actions sur l'athlète (suppression d'une entrée de course, renommer l'athlète, changer le club de l'athlète, etc.) ; le ou les boutons de modification ne doivent être visibles que si et seulement si je suis connecté avec les bons pouvoirs. »

## Contexte et intention

La page publique d'un coureur (`/athletes/<id>`) est l'écran où une erreur de
données **se voit** : un nom mal orthographié par le chronométreur, un résultat
qui n'appartient pas à ce coureur, un club périmé. Aujourd'hui, la corriger
impose de quitter la page, d'ouvrir le back-office, de retrouver le coureur par
une recherche, puis de revenir vérifier. Les gestes correctifs existent déjà et
sont gardés ; ce qui manque, c'est leur **point d'accès là où le problème est
constaté**.

La feature ne crée donc pas un nouveau pouvoir d'administration : elle rapproche
des gestes existants de leur lieu de constat, et pose la règle de visibilité qui
va avec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Corriger l'identité d'un coureur depuis sa page (Priority: P1)

Un administrateur consulte la fiche d'un coureur et constate que le
chronométreur a écrit « LEMEE Jean-marc » au lieu de « Lemée Jean-Marc ». Il
ouvre l'édition depuis la page elle-même, corrige nom, prénom et — si besoin —
date de naissance, enregistre, et voit la page refléter la correction sans avoir
à la recharger à la main.

**Why this priority**: c'est le geste le plus fréquent, le plus visible du
public, et celui qui est aujourd'hui le plus coûteux à atteindre. Livré seul, il
justifie déjà la feature.

**Independent Test**: se connecter avec le pouvoir d'écriture sur les coureurs,
ouvrir une fiche, renommer, constater le nouveau nom sur la page et dans la
recherche publique.

**Acceptance Scenarios**:

1. **Given** je suis connecté avec le pouvoir de correction d'identité,
   **When** j'ouvre la page d'un coureur,
   **Then** un accès aux actions d'administration est visible sur la page.
2. **Given** cet accès est ouvert,
   **When** je corrige le nom et j'enregistre,
   **Then** la page affiche l'identité corrigée et me confirme l'enregistrement.
3. **Given** la correction viserait une identité déjà portée par un autre
   coureur (mêmes nom, prénom et date de naissance),
   **When** j'enregistre,
   **Then** le geste est refusé avec un message qui nomme le conflit, **rien
   n'est modifié**, et ma saisie est conservée pour que je puisse la corriger.
4. **Given** je porte le pouvoir de correction mais **pas** celui de lecture de
   l'identité complète,
   **Then** la date de naissance ne m'est jamais affichée, et l'enregistrement
   n'efface pas la date existante.

---

### User Story 2 - Supprimer un résultat erroné depuis la page du coureur (Priority: P2)

Un administrateur voit sur la fiche un résultat qui n'a rien à y faire — une
saisie manuelle en double, une ligne fabriquée par un import raté. Il le
supprime depuis la ligne du tableau, après une confirmation qui nomme ce qui va
disparaître.

**Why this priority**: c'est la seconde erreur la plus visible, et la seule qui
soit **irréversible** — d'où la confirmation explicite et le journal.

**Independent Test**: se connecter avec le pouvoir de suppression de résultat,
supprimer une ligne du tableau, constater sa disparition, les compteurs de la
page recalculés, et l'entrée correspondante au journal d'administration.

**Acceptance Scenarios**:

1. **Given** je porte le pouvoir de suppression de résultat,
   **When** je consulte le tableau des épreuves du coureur,
   **Then** chaque ligne offre une action de suppression.
2. **Given** je déclenche la suppression,
   **When** l'écran me demande confirmation,
   **Then** il nomme l'épreuve concernée et l'irréversibilité du geste, et rien
   n'est supprimé tant que je n'ai pas confirmé.
3. **Given** j'ai confirmé la suppression d'un résultat **validé**,
   **Then** la ligne disparaît, les indicateurs de la page (nombre d'épreuves,
   meilleure place, meilleur ratio, top 10, format favori) sont recalculés, et
   le geste est consigné au journal d'administration avec son auteur.
4. **Given** je supprime le dernier résultat du coureur,
   **Then** la fiche reste accessible et annonce l'absence de résultat ; **le
   coureur n'est pas supprimé** par ce geste.
5. **Given** un autre administrateur a déjà supprimé ce résultat,
   **When** je confirme,
   **Then** l'écran m'annonce que le résultat n'existe plus, sans erreur
   technique brute, et la page se remet à jour.
6. **Given** j'ai confirmé la suppression d'un résultat **en attente de
   validation**,
   **Then** la ligne disparaît, mais **aucun des cinq indicateurs ne bouge** :
   ils ne portent que sur les résultats validés. L'écran ne MUST PAS laisser
   croire que le geste a échoué (FR-015 se lit sur la ligne, pas sur les
   compteurs).

---

### User Story 3 - Changer le club actuel d'un coureur (Priority: P3)

Un coureur a changé de club, ou son club a été mal orthographié à l'import.
L'administrateur corrige le **club actuel** du coureur depuis sa page.

**Why this priority**: l'effet est réel mais plus étroit que les deux précédents
— il porte sur l'appartenance affichée et sur la liste des coureurs du club, pas
sur les résultats déjà enregistrés.

**Independent Test**: corriger le club d'un coureur vers le libellé du TCN, puis
constater son apparition dans la liste des coureurs du club ; le corriger vers
un autre club et constater sa disparition.

**Acceptance Scenarios**:

1. **Given** je porte le pouvoir de correction d'identité,
   **When** j'édite le club actuel du coureur et j'enregistre,
   **Then** la page affiche le nouveau club et la liste des coureurs du club est
   cohérente avec ce changement.
2. **Given** je vide le champ club,
   **Then** le coureur est enregistré sans club actuel, et non avec un libellé
   vide traité comme un club à part entière.
3. **Given** le club porté par chaque **résultat** (le club au moment de la
   course),
   **When** je change le club actuel du coureur,
   **Then** **aucun résultat passé n'est réécrit** : l'historique conserve le
   club de l'époque, et les statistiques de club calculées sur les résultats ne
   bougent pas.
4. **Given** j'ai corrigé le club à la main,
   **When** une épreuve où ce coureur figure est réimportée avec l'ancien
   libellé de club,
   **Then** ma correction **tient** : le club actuel du coureur n'est pas réécrit.
5. **Given** un coureur dont le club n'a **jamais** été corrigé à la main,
   **When** une épreuve où il figure est importée avec un libellé de club,
   **Then** son club actuel suit l'import, comme aujourd'hui.

---

### User Story 4 - Rattacher un résultat au bon coureur (Priority: P4)

Deux homonymes ont été confondus par le chronométreur. L'administrateur, depuis
la fiche où le résultat apparaît à tort, le rattache au coureur qui l'a
réellement couru, en le cherchant par son nom.

**Why this priority**: geste plus rare que les trois précédents, et déjà
atteignable depuis le back-office ; sa valeur ici est d'être au même endroit que
les autres.

**Independent Test**: rattacher un résultat depuis la fiche A vers le coureur B,
constater sa disparition de A et son apparition sur la fiche de B.

**Acceptance Scenarios**:

1. **Given** je porte le pouvoir de réattribution de résultat,
   **When** je choisis un autre coureur pour ce résultat et je valide,
   **Then** le résultat quitte la fiche courante, apparaît sur celle du coureur
   désigné, et le geste est consigné au journal avec son auteur.
2. **Given** je désigne le coureur qui porte **déjà** ce résultat,
   **Then** l'écran me le dit sans rien écrire ni journaliser — une demande sans
   effet n'est pas un geste.
3. **Given** je porte le pouvoir de réattribution mais **pas** celui de lecture
   de l'identité complète,
   **When** je consulte le tableau des épreuves,
   **Then** aucune action de réattribution ne m'est offerte — ni ici, ni dans le
   back-office, qui me l'offre aujourd'hui pour me la refuser ensuite. Le geste
   exige les deux pouvoirs (FR-004, FR-020).

---

### User Story 5 - Ne voir que ce que l'on peut faire (Priority: P1)

Un visiteur anonyme, un membre connecté sans pouvoir d'administration, et un
administrateur ne portant qu'**un** des pouvoirs concernés voient trois pages
différentes : rien pour les deux premiers, la seule action correspondant à son
pouvoir pour le troisième.

**Why this priority**: c'est la contrainte explicite de l'issue (« si et
seulement si »), et elle conditionne toutes les autres histoires. Elle est P1 à
égalité avec US1 : sans elle, US1 annonce au public des gestes qu'il ne peut pas
faire.

**Independent Test**: charger la même fiche dans quatre états de session
(anonyme, connecté sans pouvoir, porteur d'un seul pouvoir, porteur de tous) et
comparer les actions offertes.

**Acceptance Scenarios**:

1. **Given** je ne suis pas connecté,
   **When** j'ouvre la page d'un coureur,
   **Then** aucune action d'administration n'est visible, et la page est
   identique à ce qu'elle est aujourd'hui pour le public.
2. **Given** je suis connecté sans aucun des pouvoirs concernés,
   **Then** aucune action d'administration n'est visible.
3. **Given** je porte le pouvoir de suppression de résultat mais pas celui de
   correction d'identité,
   **Then** je vois l'action de suppression sur chaque ligne et **pas** l'accès
   à la correction d'identité — la visibilité se décide **pouvoir par pouvoir**,
   jamais « connecté / pas connecté ».
4. **Given** l'état de ma session n'a pas pu être déterminé,
   **Then** aucune action n'est offerte — une session illisible n'est pas une
   session sans pouvoirs, et l'écran ne prétend ni l'un ni l'autre.
5. **Given** un appelant contourne l'interface et demande directement un geste
   qu'il n'a pas le droit de faire,
   **Then** le geste est refusé et rien n'est modifié : **le masquage d'un
   bouton n'est pas une protection**, il évite d'annoncer un geste qui échouerait.

---

### Edge Cases

- **Le club corrigé à la main est écrasé au prochain import**, aujourd'hui : tout
  import contenant ce coureur avec un libellé de club met à jour son club actuel.
  Tranché : **la correction manuelle prime** (FR-018). Sans cela, l'action
  promise à l'administrateur ne tient que jusqu'au prochain scrape d'une épreuve
  où le coureur figure, sans que rien ne l'annonce.
- **Résultat en attente de validation** : la fiche du coureur est la seule
  surface où il s'affiche. Les actions d'administration s'y appliquent comme aux
  autres lignes ; leur validation et leur rejet restent hors périmètre (voir
  *Hors périmètre*).
- **Le coureur affiché n'existe plus** (supprimé entre-temps par un autre
  administrateur) : la page l'annonce, aucune action n'est proposée dans le vide.
- **Renommage vers une identité incomplète** : un nom vide n'est pas une
  correction ; le geste est refusé sans rien modifier.
- **Espaces superflus** dans une saisie : ils ne créent pas un coureur distinct
  de son homonyme correctement saisi.
- **Consultation sur mobile** : les actions restent atteignables sur le tableau
  des épreuves, qui défile horizontalement.

## Requirements *(mandatory)*

### Functional Requirements

**Actions offertes**

- **FR-001**: La page d'un coureur MUST offrir la correction de son identité —
  nom, prénom, date de naissance — à qui porte le pouvoir de correction des
  coureurs.
- **FR-002**: La page d'un coureur MUST offrir la correction de son **club
  actuel** au même pouvoir que FR-001.
- **FR-003**: Le tableau des épreuves MUST offrir, ligne par ligne, la
  suppression définitive du résultat à qui porte le pouvoir de suppression de
  résultat.
- **FR-004**: Le tableau des épreuves MUST offrir, ligne par ligne, la
  réattribution du résultat à un autre coureur à qui porte **à la fois** le
  pouvoir de réattribution **et** celui de lecture de l'identité complète. Les
  deux sont **couplés** : désigner le coureur cible suppose de départager deux
  homonymes, ce que seule la lecture de l'identité complète permet — et
  réattribuer au mauvais homonyme est exactement l'erreur que ce geste corrige.
- **FR-005**: L'ensemble des actions offertes sur cette page est **fermé** aux
  quatre ci-dessus. Tout autre geste correctif reste atteignable depuis le
  back-office et n'est pas dupliqué ici.

**Visibilité et autorisation**

- **FR-006**: Chaque action MUST être visible **si et seulement si** la session
  courante porte le pouvoir exigé par cette action, évalué **action par
  action** — jamais un échelon unique « administrateur », jamais le seul fait
  d'être connecté.
- **FR-007**: Un visiteur anonyme MUST voir la page strictement telle qu'elle
  est aujourd'hui, sans aucune trace des actions d'administration.
- **FR-008**: Une session dont l'état n'a pas pu être déterminé MUST être
  traitée comme n'offrant aucune action, sans affirmer pour autant que
  l'utilisateur ne porte aucun pouvoir.
- **FR-009**: Chaque geste MUST rester refusé côté serveur pour qui ne porte pas
  le pouvoir, indépendamment de ce que l'interface affiche.
- **FR-020**: L'écran du back-office qui offre **déjà** la réattribution MUST
  être aligné sur la règle de FR-004. Il n'exige aujourd'hui que le pouvoir de
  réattribution, alors que son sélecteur de coureur cible a besoin de la lecture
  de l'identité complète : il annonce donc un geste qui échoue, ce que FR-006
  proscrit. La règle de visibilité d'un geste ne MUST PAS différer d'un écran à
  l'autre.

**Effets, garanties et traces**

- **FR-010**: Une correction d'identité MUST être refusée si elle rend le
  coureur indiscernable d'un autre coureur existant, **sans rien modifier**, et
  la saisie de l'opérateur MUST être conservée à l'écran.
- **FR-011**: Une suppression de résultat MUST exiger une confirmation explicite
  qui nomme l'épreuve concernée et l'irréversibilité du geste.
- **FR-012**: Une suppression de résultat MUST NOT supprimer le coureur, même
  s'il n'a plus aucun résultat.
- **FR-013**: Un changement de club actuel MUST NOT modifier le club porté par
  les résultats déjà enregistrés.
- **FR-014**: Chacun des quatre gestes MUST être consigné au journal
  d'administration avec son auteur et sa cible ; **un geste sans effet ne MUST
  PAS produire d'entrée**, et un geste refusé ne MUST NI écrire au journal NI
  modifier la donnée.
- **FR-015**: Après un geste réussi, la page MUST refléter le nouvel état — y
  compris les indicateurs calculés — sans que l'opérateur ait à la recharger.
- **FR-016**: Un geste portant sur une ressource qui n'existe plus MUST produire
  un message compréhensible et une remise à jour de la page, jamais une erreur
  technique brute.
- **FR-017**: Les libellés, confirmations et messages d'erreur affichés MUST
  être en français.
- **FR-018**: Un club actuel **corrigé à la main** MUST survivre aux imports
  ultérieurs : aucun import ne MUST le réécrire, même s'il porte pour ce coureur
  un libellé de club différent. Un coureur dont le club n'a **jamais** été
  corrigé à la main MUST continuer de suivre l'import, comme aujourd'hui.
- **FR-019**: La distinction « club suivi par l'import » / « club figé par une
  correction » MUST être portée par la donnée elle-même, et non déduite de la
  présence d'une entrée au journal — le journal est une trace, pas un état.

### Key Entities

- **Coureur** : identité (nom, prénom, date de naissance) et **club actuel**. La
  date de naissance est la seule donnée personnelle fermée du site ; le triplet
  d'identité est aussi ce qui empêche deux fiches pour la même personne. Le club
  actuel porte en plus un état : **suivi par l'import** (défaut) ou **figé par
  une correction humaine** (FR-018/FR-019).
- **Résultat** : le rattachement d'un coureur à une épreuve, avec son
  classement, son temps et le **club porté au moment de la course** — distinct
  du club actuel du coureur.
- **Pouvoir** : l'unité d'autorisation. Quatre sont en jeu ici : lecture de
  l'identité complète, correction d'un coureur, suppression d'un résultat,
  réattribution d'un résultat.
- **Journal d'administration** : la trace de ce qui a été fait, par qui, sur
  quoi. C'est ce qui reste d'un geste irréversible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Corriger le nom d'un coureur constaté faux se fait **sans quitter
  sa page** : 0 navigation intermédiaire, contre 3 aujourd'hui (page → back-office
  → recherche → retour).
- **SC-002**: Les quatre actions sont atteignables en **au plus 2 interactions**
  depuis la fiche affichée (ouvrir l'accès, déclencher le geste), confirmation
  non comptée.
- **SC-003**: Sur les états de session testés (anonyme, connecté sans pouvoir,
  porteur d'un seul pouvoir, porteur des quatre), le nombre d'actions offertes
  est **exactement** celui des pouvoirs qui **suffisent** à un geste — vérifié
  pour les quatre pouvoirs pris un par un. Un pouvoir **couplé** compte pour zéro
  action tant que son binôme manque : le pouvoir de réattribution porté seul
  offre 0 action (FR-004), et le pouvoir de correction porté seul offre la
  correction **sans** le champ de date de naissance (US1-AC4).
- **SC-004**: Pour un visiteur anonyme, la page ne coûte **rien de plus** qu'aujourd'hui :
  même volume de données chargées et même mode de rendu qu'avant la feature.
- **SC-005**: 100 % des gestes réussis apparaissent au journal d'administration
  avec leur auteur ; 100 % des gestes refusés n'y apparaissent pas et laissent la
  donnée inchangée.
- **SC-006**: Aucune suppression de résultat n'est possible sans une confirmation
  distincte du clic initial (mesuré : 0 suppression en une seule interaction).
- **SC-007**: Après chacun des quatre gestes, l'écran est à jour sans
  rechargement manuel (mesuré sur les indicateurs de la page pour la suppression
  et la réattribution).
- **SC-008**: Un club corrigé à la main survit à **au moins un** réimport complet
  d'une épreuve où le coureur figure avec un autre libellé de club (mesuré :
  0 réécriture), tandis qu'un club jamais corrigé continue de suivre l'import.

## Assumptions

- **Les quatre gestes existent déjà comme capacités du produit**, gardés chacun
  par son pouvoir ; cette feature leur ajoute un point d'accès et une règle de
  visibilité, elle ne redéfinit ni leur sémantique ni leur garde.
- **Le « etc. » de l'issue est borné** aux quatre actions de FR-001 à FR-004
  (tranché avec le demandeur, 2026-08-20). L'édition des champs d'un résultat et
  la validation des saisies en attente sont explicitement écartées : la première
  dupliquerait la logique de l'écran des bénévoles, la seconde offrirait un
  second chemin vers un geste qui a déjà son propre contrôle d'accès.
- **Le club actuel du coureur et le club d'un résultat sont deux données
  distinctes**, et l'issue (« changer le club de l'athlète ») porte sur la
  première.
- **La suppression d'un résultat est irréversible** : aucune corbeille, aucune
  annulation. C'est la confirmation et le journal qui en tiennent lieu.
- Les gestes s'adressent à une poignée d'administrateurs du club, sur des
  corrections ponctuelles : aucun besoin d'action de masse, de sélection
  multiple ni de file d'attente.
- L'authentification et l'attribution des pouvoirs existent et ne sont pas
  touchées ; la feature n'introduit aucun nouveau pouvoir.

## Hors périmètre

- **Validation et rejet des résultats en attente** : cela appartient à l'écran
  des bénévoles, avec sa propre porte d'entrée et son propre contrôle d'accès.
- **Édition des champs d'un résultat** (dossard, place, temps, catégorie) :
  écartée — elle dupliquerait la logique de l'écran des bénévoles, qui la borne
  aux saisies en attente.
- **Suppression d'un coureur** et **fusion de deux fiches en double** : gestes
  d'un autre ordre, avec un impact à mesurer avant de l'offrir.
- **Correction de l'épreuve** (nom, date, type) depuis la fiche d'un coureur :
  elle se fait depuis l'épreuve, où son ampleur est visible.
- **Journal consultable depuis l'interface** : les gestes s'y écrivent, sa
  lecture reste hors de cette feature.
- **Le back-office**, à **une exception près** : l'alignement de la visibilité de
  la réattribution exigé par FR-020. C'est la contrepartie assumée de FR-004 —
  une même règle pour un même geste, sinon la spec en fabrique deux (tranché avec
  le demandeur, 2026-08-20). Rien d'autre du back-office n'est touché.

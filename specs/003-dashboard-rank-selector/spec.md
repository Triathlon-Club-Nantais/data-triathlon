# Feature Specification: Sélecteur de type de rang sur les cartes de stats

**Feature Branch**: `feat/104-dashboard-rank-selector`

**Created**: 2026-07-29

**Status**: Draft

**Input**: Issue #104 — Sélecteur de type de rang (scratch / catégorie / genre) sur les cartes de stats du dashboard et de la page club.

## Clarifications

### Session 2026-07-29

- Q: Présentation du split Femmes / Hommes — 5 boutons distincts (Scratch / Catégorie / Femmes / Hommes / Tous), ou 4 boutons avec dédoublement F/H des cartes quand « Genre » est actif ? → A: 4 boutons avec dédoublement F/H (option B). Choix itératif — on pourra basculer sur 5 boutons plus tard si le dédoublement dessert l'UX.
- Q: Sémantique du mode « Tous » — min-des-trois (comportement actuel, préserve la garantie #77), somme-des-trois, ou retrait du mode ? → A: Min-des-trois (option A). Une participation compte au maximum 1 fois par carte : `victoires++` si `min(rank_overall, rank_category, rank_gender) ≤ 1`. Préserve l'emboîtement victoires ≤ podiums ≤ top 10.
- Q: Comportement de la liste des podiums récents (page club) selon le rank ? → A: Liste filtrée par rank, mode Tous garde le mélange (option A). `?rank=scratch` → podiums scratch seulement ; `?rank=category` → podiums catégorie ; `?rank=gender` → podiums genre (F et H mélangés) ; `?rank=all` → mélange des trois scopes (comportement actuel). La liste est alignée sur les cartes affichées juste au-dessus.

## Contexte

Sur `/dashboard` et `/club`, les stats « Victoires / Podiums / Top 10 » calculent aujourd'hui un rang « agrégé » : pour chaque participation, on prend le meilleur des trois classements disponibles (scratch, catégorie, genre) et on compte 1er / top-3 / top-10 sur ce minimum. Le libellé secondaire des cartes le résume par « scratch, genre ou catégorie ». Cette agrégation préserve une garantie d'emboîtement voulue par l'issue #77 : victoires ≤ podiums ≤ top 10.

Ce comportement empêche de comparer les statistiques du club avec celles présentées à l'Assemblée Générale, qui n'utilisaient **que** le rang scratch. Il masque aussi les performances catégorielles ou de genre, qui sont pourtant deux angles de lecture différents et légitimes des résultats de course.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Comparer les stats du club au bilan présenté en AG (Priority: P1)

En tant que membre du club consultant le tableau de bord, je veux pouvoir n'afficher les stats « Victoires / Podiums / Top 10 » qu'au **classement scratch**, afin de reproduire à l'identique les chiffres présentés par les bénévoles lors de l'AG et de valider mon propre calcul.

**Why this priority**: C'est le cas d'usage nominal cité dans l'issue et le seul concret que nous ayons aujourd'hui. Il justifie à lui seul la feature. Le comportement par défaut du toggle doit donc être « Scratch ».

**Independent Test**: Depuis `/dashboard`, sélectionner « Scratch » dans le toggle. Les trois cartes affichent le nombre de participations où le rang scratch atteint 1 / 3 / 10. Confirmable en comparant à `SELECT COUNT(*) FROM participations WHERE rank_overall <= 10 AND is_tcn=true` sur la saison courante.

**Acceptance Scenarios**:

1. **Given** je consulte `/dashboard` sans paramètre `?rank=`, **When** la page se charge, **Then** le toggle est positionné sur « Scratch » et les cartes reflètent le rang scratch uniquement.
2. **Given** je consulte `/dashboard?rank=scratch`, **When** la page se charge, **Then** le libellé sous les cartes indique « scratch » (et non plus « scratch, genre ou catégorie »).
3. **Given** je consulte `/club` sans paramètre `?rank=`, **When** la page se charge, **Then** le toggle est également sur « Scratch » (les deux pages sont cohérentes).

---

### User Story 2 — Regarder les stats par catégorie d'âge (Priority: P2)

En tant que membre du club, je veux basculer les stats sur le **classement catégorie** (M2, S4, V1…) afin de mesurer les performances des athlètes dans leur tranche d'âge, ce qui donne un signal différent du scratch.

**Why this priority**: Deuxième cas d'usage naturel une fois le toggle en place. N'a pas la même urgence produit que le cas AG, mais partage exactement la même mécanique — la couvrir n'ajoute quasi rien au coût.

**Independent Test**: Depuis `/dashboard`, sélectionner « Catégorie ». Les cartes reflètent alors `rank_category` uniquement. L'URL passe à `/dashboard?rank=category` et est partageable.

**Acceptance Scenarios**:

1. **Given** je suis sur `/dashboard?rank=scratch`, **When** je clique sur « Catégorie » dans le toggle, **Then** l'URL passe à `/dashboard?rank=category` et les cartes se recalculent sur `rank_category`.
2. **Given** l'URL `/dashboard?rank=category`, **When** je copie-colle le lien dans un autre onglet, **Then** la page s'ouvre directement avec les stats catégorie sans passer par le défaut.

---

### User Story 3 — Regarder les stats par genre, ventilées Femmes / Hommes (Priority: P2)

En tant que membre du club, je veux voir les stats de podium par **genre**, et je veux qu'elles distinguent explicitement les femmes et les hommes, afin de rendre visibles les deux sous-populations sans mélange.

**Why this priority**: Même priorité que la catégorie du point de vue mécanique, mais avec une exigence supplémentaire de ventilation F / H demandée explicitement par le propriétaire de l'issue (« j'aimerais bien que la section Genre il y ait une partie femme et homme distinct »). Résolue en clarify : **4 boutons** (Scratch / Catégorie / Genre / Tous), les cartes se **dédoublent** F/H quand « Genre » est actif.

**Independent Test**: Depuis `/dashboard?rank=gender`, chacune des trois cartes affiche deux compteurs distincts : Femmes (participations où `rank_gender` atteint 1 / 3 / 10 pour un athlète femme) et Hommes (idem pour un athlète homme).

**Acceptance Scenarios**:

1. **Given** je suis sur `/dashboard`, **When** je clique sur « Genre », **Then** l'URL passe à `?rank=gender` et chaque carte expose deux compteurs distincts (F et H), jamais confondus.
2. **Given** une participation d'un athlète homme classé 1er `rank_gender`, **When** j'affiche les stats femmes, **Then** cette participation **n'est pas comptée** (le classement genre reste séparé F / H).
3. **Given** un athlète dont le genre n'est pas renseigné en base, **When** j'affiche les stats femmes (respectivement hommes), **Then** ses participations ne sont **pas comptées** dans ce sous-ensemble.

---

### User Story 4 — Conserver la vue agrégée actuelle en option (Priority: P3)

En tant que membre du club habitué au comportement actuel, je veux pouvoir retrouver la vue agrégée « victoire = 1er sur au moins un des trois classements » via une option « Tous » du toggle, pour ne pas perdre cette lecture.

**Why this priority**: Optionnel — la valeur produit tient déjà avec P1+P2+P3. Cette histoire existe pour préserver le comportement historique en tant que choix explicite, et pour offrir une continuité aux utilisateurs qui l'avaient adopté.

**Independent Test**: Depuis `/dashboard?rank=all`, vérifier que les cartes retrouvent exactement les valeurs affichées aujourd'hui sans paramètre.

**Acceptance Scenarios**:

1. **Given** je suis sur `/dashboard?rank=all`, **When** la page se charge, **Then** les cartes affichent les mêmes valeurs qu'aujourd'hui sans paramètre, et le libellé secondaire indique « scratch, genre ou catégorie ».
2. **Given** l'ancien lien `/dashboard` (sans `?rank=`) partagé avant la feature, **When** je l'ouvre, **Then** j'obtiens la valeur par défaut (« Scratch »), pas l'ancienne agrégation — le changement de défaut est assumé et l'option « Tous » sert de trappe de compatibilité explicite si l'utilisateur en veut la valeur exacte.

---

### Edge Cases

- **Paramètre `?rank=` inconnu ou vide** (ex. `?rank=foo`, `?rank=`) : la page retombe silencieusement sur le défaut « Scratch », sans erreur, sans redirection. Le toggle affiche « Scratch » actif.
- **Athlète sans genre renseigné** : ses participations sont comptées dans « Scratch » / « Catégorie » / « Tous », mais **pas** dans « Femmes » ni « Hommes ». Aucune erreur visible.
- **Course avec `rank_gender` manquant** : la participation n'est pas comptée dans les stats genre (F ou H), mais reste comptée dans « Scratch » / « Catégorie » / « Tous » si le rang correspondant est présent.
- **Combinaison avec les autres toggles** (`?scope=`, `?seasons=`, `?sports=`) : le paramètre `?rank=` compose avec les autres sans les remplacer ni les ignorer. Les cartes reflètent l'intersection des filtres.
- **Aucune participation à afficher pour le rank sélectionné** (ex. `Femmes` sur un scope sans athlète femme) : les trois cartes affichent 0 sans erreur, avec leur libellé secondaire adapté.
- **Interaction avec `listPodiums()` (page club)** : la liste des podiums récents doit refléter le rank choisi. Un podium catégorie ne doit pas apparaître quand l'utilisateur a demandé « Scratch ». Voir Assumptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Un toggle « type de rang » doit être visible et opérable sur `/dashboard` et sur `/club`, placé au-dessus des cartes de stats « Victoires / Podiums / Top 10 ».
- **FR-002**: Le choix du toggle doit persister dans l'URL sous forme d'un paramètre `?rank=…`, de manière à ce qu'un lien copié-collé rouvre la page dans le même état.
- **FR-003**: Le défaut du toggle, en absence de paramètre `?rank=` ou en présence d'une valeur inconnue, doit être **« Scratch »**.
- **FR-004**: Le mode **Scratch** doit compter, pour chaque participation, un incrément « Victoires / Podiums / Top 10 » sur la seule valeur `rank_overall`.
- **FR-005**: Le mode **Catégorie** doit compter les incréments sur la seule valeur `rank_category`.
- **FR-006**: Les stats de genre doivent distinguer explicitement les femmes et les hommes : aucune participation d'un athlète homme ne doit compter dans les stats femmes, et réciproquement. Le toggle porte **4 boutons** (Scratch / Catégorie / Genre / Tous), URL `?rank=scratch|category|gender|all`. Quand « Genre » est actif, chacune des trois cartes se **dédouble** en F/H — soit deux valeurs côte à côte dans la même carte (ex. « Victoires : F 12 · H 34 »), soit un sous-libellé qui expose les deux compteurs — de sorte que les deux sous-populations restent visibles simultanément et jamais confondues.
- **FR-007**: Un mode **Tous** doit être proposé pour retrouver la vue agrégée historique. Sémantique : **min-des-trois** — pour chaque participation, on prend `min(rank_overall, rank_category, rank_gender)` en ignorant les valeurs manquantes, puis on incrémente une seule fois par carte (`victoires++` si `min ≤ 1`, etc.). Une participation ne peut donc jamais compter plus d'une fois dans une même carte, ce qui préserve l'emboîtement victoires ≤ podiums ≤ top 10 (garantie #77).
- **FR-008**: Le libellé secondaire des trois cartes doit refléter le mode courant — « scratch », « catégorie », « genre » ou « scratch, genre ou catégorie » — afin que l'utilisateur sache toujours quel critère est appliqué. En mode « genre », les deux compteurs F et H portent leur propre étiquette **à l'intérieur** de la carte (via un label « F » / « H » ou « Femmes » / « Hommes » clairement visible), pas via un libellé secondaire dédoublé.
- **FR-009**: Le paramètre `?rank=` doit se composer avec les autres paramètres de filtrage existants (`?scope=`, `?seasons=`, `?sports=`) sans les remplacer ni les invalider.
- **FR-010**: Sur `/club`, la liste des podiums récents (aujourd'hui produite par `listPodiums`) doit être filtrée par le rank sélectionné, en miroir des cartes juste au-dessus. Règles précises : `?rank=scratch` ne montre que les entrées où `rank_overall ≤ 3` ; `?rank=category` que celles où `rank_category ≤ 3` ; `?rank=gender` que celles où `rank_gender ≤ 3` (F et H mélangés dans la même liste, le badge de scope reste affiché pour indiquer le genre de chacun) ; `?rank=all` conserve le comportement actuel (mélange des trois scopes avec badge). Un « podium catégorie » ne doit donc **pas** apparaître quand l'utilisateur a demandé « Scratch ».
- **FR-011**: Le toggle ne doit proposer qu'un choix mono-sélection à la fois (pas de combinaison libre de plusieurs rangs).

### Key Entities

- **Type de rang** : valeur choisie par l'utilisateur, transmise via l'URL. Domaine figé : `scratch`, `category`, `gender`, `all` (FR-006). Absente ou inconnue → défaut « Scratch » (FR-003).
- **Participation** : donnée existante qui porte les trois rangs (scratch, catégorie, genre) et le lien vers l'athlète (dont le genre). Aucune modification de schéma.
- **Athlète** : donnée existante qui porte le genre (`F`, `M`, ou vide). Sert à ventiler les stats Femmes / Hommes (FR-006). Aucune modification de schéma.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un membre du club peut retrouver, en moins de 5 secondes, les chiffres exacts de « Victoires / Podiums / Top 10 » présentés à l'AG (au scratch), sans quitter le dashboard ni recalculer à la main.
- **SC-002**: Les stats affichées sur `/dashboard?rank=scratch` correspondent, à la participation près, au décompte des participations où `rank_overall` atteint 1 / 3 / 10 sur le périmètre courant (scope + seasons + sports).
- **SC-003**: Sur `/dashboard?rank=gender`, le compteur « Femmes » de chaque carte ne compte **aucune** participation d'un athlète homme, sur 100 % des cas testés. Idem pour le compteur « Hommes » vs les femmes.
- **SC-004**: 100 % des liens de la forme `/dashboard?rank=X` restent partageables (ouverts dans un onglet vierge, ils rouvrent la même vue) — cet objectif remplace toute évaluation par « ergonomie » subjective.
- **SC-005**: Aucune régression fonctionnelle sur `/dashboard` et `/club` en l'absence de paramètre `?rank=` : la valeur par défaut est bien « Scratch », et les cartes se calculent en un seul rendu (sans loading intermédiaire), comme avant.

## Assumptions

- **Aucun changement backend** : les trois rangs (`rank_overall`, `rank_category`, `rank_gender`) et le genre de l'athlète (`athlete.gender`) sont déjà exposés dans le DTO `Participation` renvoyé par `/api/v1`. La feature est calculatoire côté client.
- **Pas de nouvelle table ni de nouveau champ** : la ventilation Femmes / Hommes se déduit de `athlete.gender` combiné à `rank_gender`.
- **Pas d'endpoint stats paramétré** : le front trie déjà toutes les participations localement (dashboard et club téléchargent la liste complète), ce principe est maintenu — pas de round-trip supplémentaire.
- **Rétro-compatibilité assumée sur le défaut** : un lien historique `/dashboard` (sans paramètre) affichait l'agrégation « scratch, genre ou catégorie ». Après la feature, il affichera « Scratch ». Ce changement est **volontaire** et cohérent avec le cas d'usage AG (FR-003, US1). Les utilisateurs qui veulent retrouver l'ancienne valeur exacte doivent utiliser `?rank=all`.
- **Pas de multi-select** : la feature couvre un choix mono-sélection uniquement (FR-011). Le multi-select est explicitement hors périmètre (option B rejetée par l'issue).
- **Portée limitée à `/dashboard` et `/club`** : les cartes « Meilleure place », « Meilleur ratio », « Top 10 » de la fiche athlète (`/athletes/[id]`) ne sont **pas** couvertes par ce toggle. Elles restent régies par leur propre logique. Une extension future à d'autres pages est possible mais n'est pas engagée ici.
- **Interaction avec `listPodiums()`** : la liste des podiums récents de `/club` doit refléter le rank choisi (FR-010). La modification de `listPodiums()` fait partie du périmètre.

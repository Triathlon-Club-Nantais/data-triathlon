# Feature Specification: Résultats en attente de validation visibles sur la page de l'épreuve

**Feature Branch**: `feat/1273-pending-results-on-course`

**Created**: 2026-10-09

**Status**: Draft

**Input**: Issue #1273. « Afficher les résultats en attente de validation sur la page de l'épreuve sans les compter. Chaque ligne en attente (non refusée) apparaît dans le tableau des résultats de l'épreuve avec la mention « En attente de validation », visuellement distincte. Elle n'entre dans aucun compte ni agrégat. Un résultat refusé n'apparaît pas. Dans les listes d'épreuves, une épreuve qui n'a que des résultats en attente le dit (« 1 résultat en attente ») au lieu de paraître vide. »

## Contexte

En production le 09/10, 17 résultats saisis à la main attendent leur validation sur
16 épreuves, et ces 16 épreuves paraissent toutes vides. Un résultat déclaré reste
exclu de tout comptage tant qu'un bénévole ne l'a pas validé (#270), et sa seule
surface d'affichage était jusqu'ici la fiche de son athlète. Conséquence : une
épreuve créée par une saisie manuelle n'affiche rien, et n'apparaît dans aucune liste
d'épreuves.

Cette feature assouplit l'invariant de #270 **pour l'affichage seulement** : la règle
qui exclut un résultat en attente de tout comptage reste le filtre unique de tous les
comptes ; une lecture distincte sert uniquement à lister les lignes de l'épreuve.

## Clarifications

### Session 2026-10-09

Mode autonome : les deux premières réponses sont des décisions de l'utilisateur, les
suivantes l'option recommandée, tranchée d'après l'issue, le code et la constitution.

- Q: Qui voit les lignes en attente sur la page de l'épreuve, tout visiteur ou les
  seuls administrateurs ? → A: Tout visiteur qui voit l'épreuve (décision de
  l'utilisateur), cohérent avec la fiche d'athlète qui les montre déjà.
- Q: Où se placent les lignes en attente dans le tableau de l'épreuve ? → A: À la fin
  du tableau, après tout le classement validé, sans rang ni écart, avec la mention «
  En attente de validation » (décision de l'utilisateur).
- Q: Dans les listes d'épreuves, la mention « N résultat(s) en attente » s'affiche-t-elle
  aussi sur une épreuve qui a déjà des résultats validés ? → A: Non. Elle remplace le
  compte de participants uniquement quand celui-ci vaut zéro ; une épreuve avec des
  résultats validés garde son affichage actuel (l'issue ne vise que l'épreuve qui
  paraît vide, et l'affichage existant ne change pas).
- Q: Les listes d'épreuves filtrées par athlète (recherche par nom) ou par portée club
  font-elles figurer une épreuve qui n'a que des résultats en attente ? → A: Oui, si un
  de ses résultats en attente satisfait le filtre, exactement comme un résultat validé
  le ferait ; sinon non.
- Q: Le nombre d'épreuves affiché en tête des listes compte-t-il une épreuve qui n'a que
  des résultats en attente ? → A: Oui : c'est une épreuve listée (le défilement infini
  s'arrête sur ce nombre), pas un résultat. Le total des résultats, lui, ne compte que
  des résultats validés.

## User Scenarios & Testing *(mandatory)*

### User Story 1 : voir les résultats en attente sur la page de l'épreuve (Priority: P1)

Un visiteur (membre, bénévole ou administrateur, sans droit particulier) ouvre la page
d'une épreuve qui porte des résultats saisis à la main non encore validés. Il voit ces
lignes dans le tableau des résultats, après le classement validé, chacune marquée « En
attente de validation », sans rang ni écart, et les comptes de l'épreuve (participants,
finishers, athlètes TCN, répartitions) restent ceux des seuls résultats validés.

**Why this priority**: c'est le défaut constaté (épreuves vides alors qu'elles portent
des résultats), et le seul moyen pour un administrateur sans droit de valider de voir ce
que contient l'épreuve.

**Independent Test**: créer une épreuve avec un résultat validé et un résultat en
attente, ouvrir sa page : le validé est classé, le résultat en attente suit avec la
mention, et le compteur « Participants » vaut 1.

**Acceptance Scenarios**:

1. **Given** une épreuve avec 2 résultats validés et 1 résultat en attente, **When** un
   visiteur ouvre sa page, **Then** le tableau montre les 2 résultats classés puis la
   ligne en attente, marquée « En attente de validation », sans rang ni écart, et le
   compteur de participants affiche 2.
2. **Given** une épreuve qui n'a qu'un résultat en attente, **When** un visiteur ouvre
   sa page, **Then** le tableau montre cette ligne avec la mention, au lieu d'un état
   vide.
3. **Given** une épreuve avec un résultat en attente puis refusé par un bénévole,
   **When** un visiteur ouvre sa page, **Then** ce résultat n'apparaît pas.
4. **Given** un classement paginé sur plusieurs pages et un résultat en attente,
   **When** le visiteur feuillette, **Then** la ligne en attente apparaît sur la
   dernière page, après le dernier résultat validé, et le total de la pagination ne la
   compte pas.
5. **Given** un résultat en attente, **When** un bénévole le valide, **Then** il
   rejoint le classement à son rang et la mention disparaît.

---

### User Story 2 : une épreuve sans résultat validé ne paraît plus vide dans les listes (Priority: P2)

Dans les listes d'épreuves (page Résultats, derniers résultats enregistrés de « Ajouter
», épreuves récentes du tableau de bord), une épreuve qui n'a que des résultats en
attente apparaît, avec la mention « 1 résultat en attente » (« N résultats en attente »
au pluriel) au lieu d'un compte de participants à zéro.

**Why this priority**: sans elle, l'épreuve créée par une saisie manuelle reste
introuvable depuis les listes ; la page de l'épreuve (US1) n'est atteignable que par la
fiche d'athlète.

**Independent Test**: créer une épreuve dont le seul résultat est en attente ; elle
figure dans la liste des épreuves avec « 1 résultat en attente » et le total de
résultats de la page n'a pas bougé.

**Acceptance Scenarios**:

1. **Given** une épreuve dont l'unique résultat est en attente, **When** un visiteur
   consulte la liste des épreuves, **Then** l'épreuve apparaît avec « 1 résultat en
   attente » et ne montre pas « 0 participant ».
2. **Given** la même épreuve, **When** le visiteur lit le total des résultats de la
   liste, **Then** ce total ne compte pas le résultat en attente.
3. **Given** une épreuve dont l'unique résultat en attente a été refusé, **When** un
   visiteur consulte la liste des épreuves, **Then** l'épreuve n'apparaît pas.
4. **Given** une épreuve avec des résultats validés et un résultat en attente, **When**
   elle est listée, **Then** son compte de participants et son compte TCN restent ceux
   des seuls résultats validés.

---

### User Story 3 : aucun agrégat ne compte un résultat en attente (Priority: P1)

Les statistiques, saisons, podiums, classement du club, compteurs d'épreuve et la file
qualité continuent d'ignorer tout résultat en attente.

**Why this priority**: c'est l'invariant d'intégrité de #270 ; l'afficher ne doit rien
compter.

**Independent Test**: avec un résultat en attente seul sur une épreuve, vérifier que
chacun des comptes listés en FR-006 est inchangé par rapport à la même base sans ce
résultat.

**Acceptance Scenarios**:

1. **Given** un résultat en attente, **When** on lit les compteurs de son épreuve
   (participants, TCN), la synthèse, les statistiques, les saisons, les podiums, le
   classement du club, les rangs et écarts de l'épreuve et la file qualité, **Then**
   aucun ne le compte.

### Edge Cases

- Un résultat en attente et filtré : la recherche par nom, la portée club, le filtre de
  club et de catégorie s'appliquent aussi aux lignes en attente (une recherche qui
  trouve la ligne la montre, une recherche qui ne la trouve pas la masque).
- Une épreuve avec beaucoup de résultats validés : les lignes en attente ne se
  montrent qu'en fin de classement (dernière page), jamais intercalées.
- Un résultat en attente qui porte un rang déclaré : ce rang n'est pas affiché, ni
  utilisé pour un écart.
- Un relais en attente : même traitement qu'une ligne individuelle.
- Une épreuve dont tous les résultats sont refusés : elle reste absente des listes et
  sa page montre l'état vide existant.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La page d'une épreuve MUST afficher chaque résultat en attente de
  validation non refusé de cette épreuve, dans le tableau des résultats.
- **FR-002**: Chaque ligne en attente MUST porter la mention « En attente de validation
  », distincte au premier coup d'œil des lignes validées, sans survol ni clic.
- **FR-003**: Les lignes en attente MUST se placer après tout le classement validé (en
  fin de dernière page du classement paginé), sans rang ni écart affichés.
- **FR-004**: Un résultat refusé (signalé non conforme) MUST n'apparaître ni sur la page
  de l'épreuve ni dans les listes d'épreuves.
- **FR-005**: Les filtres du classement (recherche par nom, portée club, club,
  catégorie) MUST s'appliquer aussi aux lignes en attente.
- **FR-006**: Un résultat en attente MUST n'entrer dans aucun compte ni agrégat : compte
  de participants et compte TCN d'une épreuve, total du classement paginé, synthèse
  d'épreuve, rangs et écarts, classement du club, statistiques, saisons, podiums, file
  qualité de l'administration.
- **FR-007**: Les listes d'épreuves MUST faire figurer une épreuve qui n'a que des
  résultats en attente non refusés, avec la mention « N résultat(s) en attente » à la
  place du compte de participants.
- **FR-008**: Une épreuve listée qui porte à la fois des résultats validés et en
  attente MUST garder son affichage actuel (compte de participants validés, sans
  mention) ; la mention « N résultat(s) en attente » ne remplace le compte que lorsque
  celui-ci vaut zéro.
- **FR-012**: Les filtres des listes d'épreuves portant sur les résultats (recherche
  par athlète, portée club) MUST s'appliquer aux résultats en attente comme aux
  résultats validés pour décider si une épreuve est listée.
- **FR-013**: Le nombre d'épreuves listées MUST compter une épreuve qui n'a que des
  résultats en attente ; le total des résultats MUST ne compter que des résultats
  validés.
- **FR-009**: Les lignes en attente MUST être visibles de toute personne qui voit
  l'épreuve, sans droit particulier (cohérent avec la fiche d'athlète).
- **FR-010**: Le contrat de l'API publique MUST s'étendre sans rien retirer ni changer
  de sens : les champs existants gardent leur valeur actuelle, les ajouts sont
  facultatifs pour l'appelant.
- **FR-011**: Le droit de valider et la saisie manuelle restent inchangés.

### Key Entities

- **Résultat en attente** : un résultat déclaré, non encore validé, non refusé. Porte
  athlète, épreuve, statut, temps et éventuellement un rang déclaré (non affiché).
- **Épreuve** : porte des comptes validés (participants, TCN) et désormais un nombre de
  résultats en attente, qui n'est jamais un compte de participants.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Les 16 épreuves de production qui ne portent qu'un résultat en attente
  montrent ce résultat sur leur page, et chacune apparaît dans la liste des épreuves
  avec la mention « résultat en attente ».
- **SC-002**: 0 compte ou agrégat parmi ceux listés en FR-006 ne varie lorsqu'on ajoute
  un résultat en attente, vérifié par un test automatisé par agrégat.
- **SC-003**: Un visiteur distingue une ligne en attente d'une ligne validée sans
  interaction (mention lisible en permanence, contraste conforme WCAG AA).
- **SC-004**: Aucun appelant existant de l'API ne voit changer la valeur d'un champ
  qu'il lit déjà.

## Assumptions

- Les résultats en attente sont peu nombreux par épreuve (17 au total en production) :
  ils sont tous rendus d'un coup, sans pagination propre.
- La carte et les statistiques ne changent pas. La frise de couverture de la page
  Résultats compte des épreuves listées : elle inclut une épreuve qui n'a que des
  résultats en attente, comme le nombre d'épreuves.
- La mention réutilise le marqueur visuel « En attente de validation » déjà présent sur
  la fiche d'athlète.

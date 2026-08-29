# Feature Specification: Compteurs de saison distincts + validation humaine du quota club

**Feature Branch**: `20260828-134141-club-season-counters`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "Issue GitHub #709 — feat(club/athletes): season counters breakdown + human season validation (3 races + volunteering)"

## Clarifications

### Session 2026-08-28

- Q: Un athlète peut-il avoir plusieurs actions de bénévolat déclarées pour la même saison, ou une seule déclaration suffit-elle ? → A: Plusieurs déclarations possibles par athlète/saison (journal) ; le barème est satisfait dès qu'il y en a ≥ 1. Seuls les titulaires du pouvoir dédié (FR-007) peuvent en ajouter.
- Q: Une fois la saison d'un athlète validée, un titulaire du pouvoir peut-il la dévalider ? → A: Oui — la dévalidation est possible par un titulaire du pouvoir dédié et tracée dans `AdminActionLog` comme la validation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compteurs de saison fiables sur la liste des athlètes du club (Priority: P1)

Un administrateur ou bénévole consultant `/club/athletes` voit, pour chaque
athlète, un nombre d'épreuves de la saison qui reflète la réalité de son
activité — pas seulement les épreuves où le fournisseur de chronométrage a
publié l'affiliation club sur la ligne de résultat.

**Why this priority**: C'est le défaut mesuré qui déclenche l'issue — 39 % du
roster (122/315 athlètes) est sous-compté, ce qui rend la liste inutilisable
pour juger de l'activité réelle d'un athlète. Sans ce volet, le second (la
validation du quota) s'appuierait sur un chiffre faux.

**Independent Test**: Peut être testé et livré seul — consulter la fiche
« Ma saison » d'un athlète connu pour être sous-compté (ex. un athlète ayant
couru une épreuve Audencia La Baule ou Ironman 70.3 Les Sables d'Olonne cette
saison), noter son total réel, puis vérifier que ce même total apparaît sur
`/club/athletes` sous un libellé distinct du compteur « affiliées club ».

**Acceptance Scenarios**:

1. **Given** un athlète du club a couru 5 épreuves cette saison dont 2 sans
   affiliation club publiée par le fournisseur, **When** un administrateur
   consulte `/club/athletes`, **Then** il voit un total de 5 épreuves de
   saison pour cet athlète (pas 3).
2. **Given** un athlète a 4 épreuves dont une encore en attente de validation
   bénévole (`is_pending_validation=True`), **When** l'administrateur consulte
   `/club/athletes`, **Then** le compteur « épreuves validées » affiche 3, et
   le total réel affiche 4, sous deux libellés distincts.
3. **Given** un athlète a couru 2 épreuves dont l'affiliation club a été
   publiée par le fournisseur sur les deux, **When** l'administrateur
   consulte `/club/athletes`, **Then** le compteur « affiliées club » et le
   total réel affichent tous deux 2 (aucune divergence quand la donnée
   source est complète).
4. **Given** un athlète du club consulte sa propre fiche « Ma saison »,
   **When** la page se charge, **Then** le total affiché est inchangé par
   cette fonctionnalité (FR-019 : la fiche ne filtre déjà pas par club).

---

### User Story 2 - Déclarer une action de bénévolat (Priority: P2)

Un bénévole ou un administrateur peut enregistrer qu'un athlète du club a
réalisé une action de bénévolat au cours d'une saison donnée, avec une trace
de qui l'a déclarée et quand.

**Why this priority**: Prérequis obligatoire de la User Story 3 — sans
mécanisme de déclaration du bénévolat, il n'existe aucune donnée sur laquelle
fonder une validation de quota, puisque le barème exige explicitement une
action de bénévolat en plus des 3 courses.

**Independent Test**: Peut être testé indépendamment de la User Story 3 — un
titulaire du pouvoir dédié déclare une action de bénévolat pour un athlète et
une saison, puis vérifie que cette déclaration apparaît dans l'historique de
l'athlète et dans le journal d'administration (`AdminActionLog`), même sans
qu'aucune validation de saison n'ait encore eu lieu.

**Acceptance Scenarios**:

1. **Given** un titulaire du pouvoir de gestion du bénévolat consulte la
   fiche d'un athlète du club, **When** il déclare une action de bénévolat
   pour la saison en cours, **Then** l'action est enregistrée avec l'athlète,
   la saison, l'auteur de la déclaration et l'horodatage, et une entrée
   apparaît dans `AdminActionLog`.
2. **Given** un athlète a déjà une action de bénévolat déclarée pour la
   saison, **When** un titulaire du pouvoir consulte sa fiche, **Then** cette
   déclaration est visible (pas de re-déclaration silencieuse en double sans
   avertissement).
3. **Given** un utilisateur sans le pouvoir dédié, **When** il tente de
   déclarer une action de bénévolat, **Then** l'accès est refusé.

---

### User Story 3 - Valider la saison d'un athlète du club (Priority: P3)

Un titulaire du pouvoir dédié marque manuellement qu'un athlète a rempli son
quota de saison (3 courses + 1 action de bénévolat), afin que la liste des
athlètes du club puisse être triée/filtrée sur ce statut.

**Why this priority**: Objectif final de l'issue, mais dépend des deux volets
précédents pour être fiable (compteur de courses correct) et actionnable
(bénévolat déclaré). Livrable en dernier sans bloquer la valeur des User
Stories 1 et 2, qui restent utiles seules.

**Independent Test**: Peut être testé en donnant à un athlète 3 épreuves
validées et 1 action de bénévolat déclarée pour la saison, puis en
vérifiant qu'un titulaire du pouvoir dédié peut marquer sa saison comme
validée, que ce statut est visible et filtrable sur `/club/athletes`, et
qu'une entrée apparaît dans `AdminActionLog`.

**Acceptance Scenarios**:

1. **Given** un athlète a 3 épreuves validées et 1 action de bénévolat
   déclarée pour la saison, **When** un titulaire du pouvoir dédié valide sa
   saison, **Then** le statut « saison validée » est enregistré pour cet
   athlète et cette saison, avec une trace dans `AdminActionLog` (auteur,
   horodatage).
2. **Given** un athlète n'a que 2 épreuves validées pour la saison, **When**
   un titulaire du pouvoir consulte sa fiche, **Then** l'interface signale
   que le quota de courses n'est pas atteint (la validation reste un geste
   humain possible mais informé, pas un calcul qui verrouille
   automatiquement le statut).
3. **Given** plusieurs athlètes ont des statuts de validation différents
   pour la saison en cours, **When** un administrateur trie/filtre
   `/club/athletes` par statut de validation, **Then** seuls les athlètes
   correspondant au filtre s'affichent.
4. **Given** un utilisateur sans le pouvoir dédié, **When** il consulte
   `/club/athletes`, **Then** il voit le statut de validation (lecture) mais
   ne peut pas le modifier.
5. **Given** la saison d'un athlète a été validée par erreur, **When** un
   titulaire du pouvoir dédié la dévalide, **Then** le statut repasse à
   « non validée » et une entrée de dévalidation apparaît dans
   `AdminActionLog`.
6. **Given** une nouvelle saison démarre, **When** un administrateur consulte
   le statut de validation d'un athlète pour cette nouvelle saison, **Then**
   le statut est vierge (la validation d'une saison précédente ne se
   reconduit pas automatiquement).

### Edge Cases

- Un athlète change de club en cours de saison : ses épreuves antérieures au
  changement comptent-elles dans le total du club actuel ? *(hors périmètre
  de cette spec — comportement hérité, non modifié ici.)*
- Un athlète a 0 épreuve sur la saison (nouvel adhérent) : les trois
  compteurs affichent 0, sans erreur ni valeur manquante.
- Une action de bénévolat est déclarée par erreur : aucune suppression n'est
  requise par cette spec (portée : déclaration et consultation ; la
  correction d'une erreur de saisie est hors périmètre — cohérent avec
  `AdminActionLog`, lecture seule après écriture).
- Une saison est validée puis un athlète perd une épreuve validée
  (invalidation a posteriori par un bénévole) : le statut de validation déjà
  posé n'est pas retiré automatiquement (c'est un geste humain, pas un
  calcul asservi — cf. FR-011) ; seule une dévalidation manuelle par un
  titulaire du pouvoir dédié (FR-013) peut le retirer.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT calculer, pour chaque athlète du club et une
  saison donnée, un total réel d'épreuves identique à celui affiché sur la
  fiche « Ma saison » de l'athlète (sans filtre sur l'affiliation club de la
  participation).
- **FR-002**: Le système DOIT calculer, pour chaque athlète du club et une
  saison donnée, un compteur d'épreuves validées (`is_pending_validation=False`)
  parmi les épreuves de la saison.
- **FR-003**: Le système DOIT calculer, pour chaque athlète du club et une
  saison donnée, un compteur d'épreuves affiliées au club tel qu'enregistré
  sur la ligne de résultat (comportement actuel, conservé et nommé
  explicitement).
- **FR-004**: `/club/athletes` DOIT afficher ces trois compteurs sous des
  libellés distincts et non ambigus, de façon à ce qu'un utilisateur ne
  confonde pas « total réel » avec « affiliées club ».
- **FR-005**: Tout autre emplacement de l'interface affichant aujourd'hui un
  chiffre unique « X épreuves » pour un athlète du club, dérivé du même calcul
  que `/club/athletes` (compteur filtré sur l'affiliation club), DOIT être mis
  à jour pour utiliser les mêmes compteurs distincts.
- **FR-006**: Le système DOIT permettre de déclarer une action de bénévolat
  pour un athlète du club, associée à une saison, un auteur (utilisateur
  ayant effectué la déclaration) et un horodatage. Plusieurs déclarations
  DOIVENT pouvoir coexister pour le même athlète et la même saison (journal,
  pas un indicateur unique) ; le barème (FR-012) est satisfait dès qu'il en
  existe au moins une.
- **FR-007**: La déclaration d'une action de bénévolat DOIT être réservée aux
  titulaires d'un pouvoir dédié du catalogue RBAC existant
  (`app/core/permissions.py`), vérifié via `require_permission`.
- **FR-008**: Chaque déclaration d'action de bénévolat DOIT produire une
  entrée dans `AdminActionLog` (auteur, horodatage, entité concernée).
- **FR-009**: Le système DOIT permettre à un titulaire d'un pouvoir dédié de
  marquer la saison d'un athlète du club comme validée, distinctement de tout
  autre pouvoir (déclaration du bénévolat, gestion des données).
- **FR-010**: Le statut de validation de saison DOIT être conservé par
  athlète **et par saison** — la validation d'une saison n'affecte pas le
  statut d'une autre saison pour le même athlète.
- **FR-011**: La validation de saison DOIT rester un geste humain explicite :
  le système ne DOIT PAS positionner ou retirer automatiquement ce statut sur
  la base d'un recalcul des compteurs (courses ou bénévolat), même si le
  quota cesse d'être atteint après coup.
- **FR-012**: L'interface DOIT indiquer, au moment où un titulaire du pouvoir
  s'apprête à valider la saison d'un athlète, si le barème (3 épreuves
  validées + 1 action de bénévolat déclarée) est atteint pour cette saison —
  sans empêcher la validation si ce n'est pas le cas.
- **FR-013**: Le système DOIT permettre à un titulaire du pouvoir dédié de
  dévalider une saison déjà validée. Toute validation ou dévalidation d'une
  saison DOIT produire une entrée dans `AdminActionLog` (auteur, horodatage,
  athlète, saison).
- **FR-014**: `/club/athletes` DOIT permettre de trier et/ou filtrer les
  athlètes du club selon leur statut de validation de saison, pour la saison
  actuellement affichée.
- **FR-015**: La lecture du statut de validation de saison et des compteurs
  associés DOIT être accessible à tout utilisateur ayant déjà accès à
  `/club/athletes` ; seule l'écriture (déclaration de bénévolat, validation)
  est réservée aux pouvoirs dédiés (FR-007, FR-009).

### Key Entities *(include if feature involves data)*

- **VolunteerAction** *(nouvelle entité)* : une action de bénévolat déclarée
  pour un athlète, rattachée à une saison, avec l'auteur de la déclaration et
  l'horodatage. Plusieurs actions peuvent coexister pour le même athlète et
  la même saison (journal, pas un indicateur unique). Ne modélise pas de
  lien obligatoire vers une épreuve précise — la conception technique
  tranchera si un lien optionnel vers une `Course` est utile, la déclaration
  restant utilisable de façon purement déclarative.
- **SeasonValidation** *(nouvelle entité, ou attribut porté par une entité
  existante)* : le statut de validation de la saison d'un athlète du club,
  par saison — qui l'a validée, quand. Distincte du calcul des compteurs
  (FR-001 à FR-003), qui reste dérivé à la volée.
- **Athlete** *(existante, `app/models/athlete.py`)* : entité dont la fiche
  « Ma saison » sert de référence pour le total réel (FR-001) ; ne porte
  aujourd'hui aucun flag de validation de saison.
- **Participation** *(existante)* : porte `club` (affiliation déclarée par le
  fournisseur, potentiellement `NULL`) et `is_pending_validation`, les deux
  champs sources des trois compteurs.
- **AdminActionLog** *(existante, `app/models/admin_action_log.py`)* : patron
  d'audit trail réutilisé pour tracer les déclarations de bénévolat (FR-008)
  et les validations de saison (FR-013).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur `/club/athletes`, 100 % des athlètes actuellement
  sous-comptés (mesuré : 122/315, soit 39 % du roster) affichent un total
  réel d'épreuves identique à celui de leur fiche « Ma saison ».
- **SC-002**: Un utilisateur consultant `/club/athletes` peut distinguer les
  trois compteurs (validées / affiliées club / total réel) sans avoir à
  consulter une autre page, pour 100 % des athlètes listés.
- **SC-003**: Un titulaire du pouvoir dédié peut déclarer une action de
  bénévolat pour un athlète en moins de 3 interactions (ouvrir la fiche,
  déclarer, confirmer).
- **SC-004**: 100 % des déclarations de bénévolat et des validations de
  saison laissent une trace consultable (auteur + horodatage) dans le
  journal d'administration.
- **SC-005**: Un administrateur peut filtrer la liste des athlètes du club
  pour ne voir que ceux dont la saison est validée (ou non validée) en une
  seule action de filtrage.

## Assumptions

- La « saison » est le découpage déjà utilisé ailleurs dans l'application
  (ex. « 2025-26 ») ; cette spec ne redéfinit pas ses bornes.
- Le calcul des trois compteurs (FR-001 à FR-003) reste dérivé à la volée des
  données existantes (`Participation`) — cette spec ne demande pas de
  dénormalisation ou de compteur mis en cache, sauf si la conception
  technique l'estime nécessaire pour la performance.
- Le pouvoir de déclaration du bénévolat (FR-007) et le pouvoir de validation
  de saison (FR-009) sont deux pouvoirs distincts du catalogue RBAC — un
  administrateur peut avoir l'un sans l'autre. Le nom exact des codes de
  pouvoir est un détail de conception, pas de cette spec.
- Une action de bénévolat déclarative (sans lien à une épreuve précise) est
  suffisante pour satisfaire le barème ; le lien optionnel à une `Course`
  (mentionné dans l'issue comme question ouverte) est un détail de
  conception technique, pas un point bloquant pour cette spec.
- Le seuil du barème (3 courses + 1 bénévolat) est fixe pour cette version ;
  le rendre configurable par saison est hors périmètre sauf demande
  ultérieure explicite.
- Aucune notification (email, etc.) n'est requise lors d'une validation de
  saison ou d'une déclaration de bénévolat — la traçabilité via
  `AdminActionLog` suffit pour cette version.

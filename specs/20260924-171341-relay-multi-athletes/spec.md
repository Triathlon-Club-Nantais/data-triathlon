# Feature Specification: Rattacher un résultat de relais à plusieurs athlètes

**Feature Branch**: `894-relay-multi-athletes`

**Created**: 2026-09-24

**Status**: Draft

**Input**: User description: "Issue #894 (sous-issue de l'epic #889) : rattacher une participation de relais à plusieurs athlètes. Aujourd'hui une Participation porte un seul athlete_id ; un relais crée un athlète fictif au nom de l'équipe (ex. /athletes/39426 : nom de groupe seul, /athletes/102324 : « A / B »), et le résultat n'apparaît sur le profil d'aucun équipier. reassign_participation (backend/app/services/admin_actions.py) ne vise qu'un athlète. Besoin : un administrateur attribue un résultat de relais à 2 à N athlètes (existants ou créés) en un geste depuis la fiche de l'athlète fictif ; le résultat apparaît sur chaque profil ; l'athlète fictif orphelin est supprimé ; règle de décompte d'un podium de relais (compteurs individuels et club) à décider ; aucun changement pour les relais non attribués. Choix de modèle à trancher en plan : table de liaison vs une participation par équipier (patron runnerbreizh, qui publie déjà une ligne par équipier). Hors périmètre : découpage automatique à l'import (#895), reprise des relais existants."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Attribuer un relais à ses équipiers depuis la fiche de l'équipe (Priority: P1)

Un administrateur ouvre la fiche d'un « athlète » qui est en réalité une équipe de relais (par exemple « DUPONT Jean / MARTIN Paul », ou « Les Inconnus »). Sur le résultat de relais, il choisit « Attribuer aux équipiers », sélectionne les deux à N personnes qui composaient l'équipe parmi les athlètes connus, puis valide. Le résultat apparaît aussitôt sur la fiche de chaque équipier, et la fiche de l'équipe, désormais vide, disparaît.

**Why this priority**: c'est le défaut signalé (#889) : un résultat d'adhérent n'apparaît sur aucun profil. Le contournement actuel ne l'attribue qu'à une seule personne sur deux.

**Independent Test**: sur une épreuve de relais dont le résultat porte un athlète fictif au nom de l'équipe, attribuer le résultat à deux athlètes existants. Vérifier que les deux fiches affichent le résultat et que la fiche de l'équipe n'existe plus.

**Acceptance Scenarios**:

1. **Given** un résultat de relais porté par la fiche « DUPONT Jean / MARTIN Paul » et deux athlètes existants Jean DUPONT et Paul MARTIN, **When** l'administrateur attribue le résultat à ces deux athlètes, **Then** le résultat (même temps, même rang, même épreuve) apparaît sur la fiche de chacun, et la fiche « DUPONT Jean / MARTIN Paul », vidée de son unique résultat, est supprimée.
2. **Given** une fiche d'équipe qui porte **plusieurs** résultats, **When** l'administrateur n'en attribue qu'un, **Then** la fiche de l'équipe subsiste avec les résultats restants.
3. **Given** un administrateur sans le pouvoir de rattachement des résultats, **When** il consulte la fiche de l'équipe, **Then** aucune commande d'attribution ne lui est proposée.
4. **Given** l'attribution validée, **When** on consulte le journal d'administration, **Then** le geste y figure une fois, avec l'épreuve, la fiche d'origine, la liste des équipiers et la fiche purgée le cas échéant.

---

### User Story 2 - Attribuer à un équipier qui n'a pas encore de fiche (Priority: P2)

L'un des équipiers n'a jamais été importé : il n'a pas de fiche. Dans le même geste d'attribution, l'administrateur saisit son nom et son prénom, et sa fiche est créée avec le résultat de relais.

**Why this priority**: fréquent dès que l'équipe mêle un adhérent et une personne extérieure, ou un nom de groupe sans aucun nom d'équipier (#889, fiche 39426). Sans cela, le geste de la story 1 est bloqué pour ces équipes.

**Independent Test**: attribuer un résultat de relais à un athlète existant **et** à une personne saisie à la main. Vérifier que la nouvelle fiche existe et porte le résultat.

**Acceptance Scenarios**:

1. **Given** un résultat de relais et un équipier sans fiche, **When** l'administrateur saisit « MARTIN Paul » comme second équipier, **Then** une fiche Paul MARTIN est créée et porte le résultat.
2. **Given** un nom saisi qui correspond exactement à une fiche existante, **When** l'administrateur valide, **Then** le résultat est rattaché à la fiche existante et aucun doublon n'est créé.

---

### User Story 3 - Décompter un podium de relais sans fausser les chiffres (Priority: P3)

Une fois le relais attribué, le podium ou la victoire obtenue en relais suit une règle unique : il reste visible dans la liste des résultats de chaque équipier, mais n'entre pas dans ses compteurs individuels, et il compte une seule fois pour le club.

**Why this priority**: sans règle explicite, un podium de relais compterait deux fois dans les chiffres du club (une fois par équipier), et un podium en duo pèserait autant qu'un podium en solo dans les compteurs individuels. C'est secondaire par rapport à l'affichage du résultat lui-même.

**Independent Test**: attribuer un relais classé 2e à deux adhérents. Vérifier les compteurs de podiums de chacun et celui du club.

**Acceptance Scenarios**:

1. **Given** un relais classé 2e attribué à deux adhérents, **When** on consulte la fiche de chacun, **Then** le résultat figure dans la liste des résultats avec son rang, mais les compteurs individuels (podiums, victoires, top 10) ne l'incluent pas.
2. **Given** le même relais, **When** on consulte les compteurs de podiums du club, **Then** il est compté **une seule fois**, comme n'importe quel podium d'une épreuve.

---

### Edge Cases

- Un équipier choisi porte **déjà** un résultat sur cette épreuve : l'attribution est refusée en entier, avec le nom de l'équipier en cause, et rien n'est modifié.
- Le même athlète est sélectionné deux fois : l'attribution est refusée.
- Moins de deux équipiers sélectionnés : l'attribution est refusée (pour une seule personne, la réattribution existante suffit).
- Le résultat visé n'est pas un relais (épreuve individuelle) : la commande n'est pas proposée, et le serveur refuse la demande.
- La fiche d'origine est aussi l'un des équipiers choisis (la fiche porte déjà le vrai nom d'un équipier) : elle garde le résultat et n'est pas purgée.
- Deux administrateurs attribuent le même résultat en même temps : un seul geste l'emporte, l'autre reçoit un refus explicite sans état à moitié écrit.
- Un résultat de relais déjà attribué à des équipiers : on peut le corriger (retirer ou ajouter un équipier) sans repasser par une fiche d'équipe.
- Un résultat de relais non attribué reste affiché exactement comme aujourd'hui, mais sort des compteurs individuels de la fiche qui le porte (FR-011).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système MUST permettre qu'un même résultat de relais appartienne à plusieurs athlètes, chacun le voyant sur sa fiche avec le même temps, le même rang et la même épreuve.
- **FR-002**: Un administrateur qui détient le pouvoir de rattachement des résultats MUST pouvoir attribuer un résultat de relais à 2 à 8 athlètes en un seul geste, depuis la fiche qui porte ce résultat.
- **FR-003**: Le geste MUST accepter des athlètes existants et des équipiers saisis à la main (nom, prénom). Une saisie identique à une fiche existante MUST réutiliser cette fiche.
- **FR-004**: Le geste MUST être atomique : soit tous les équipiers reçoivent le résultat, soit rien ne change.
- **FR-005**: Le système MUST refuser l'attribution si un équipier porte déjà un résultat sur la même épreuve, si un athlète est choisi deux fois, si moins de deux équipiers sont choisis, ou si le résultat n'est pas un relais, avec un message en français qui dit la cause.
- **FR-006**: Après attribution, une fiche d'origine qui ne porte plus aucun résultat MUST être supprimée, selon la même règle que la réattribution existante.
- **FR-007**: Chaque attribution MUST être consignée une fois dans le journal d'administration (épreuve, fiche d'origine, équipiers, fiches créées, fiche purgée).
- **FR-008**: Un administrateur MUST pouvoir corriger la composition d'un relais déjà attribué (ajouter ou retirer un équipier, tant qu'il en reste au moins deux), sous les mêmes règles que FR-004 à FR-007. Pour ne garder qu'un athlète, la réattribution simple rend le résultat à cet athlète et vide la composition.
- **FR-009**: Le nom d'équipe publié par le chronométreur MUST rester visible sur le résultat après attribution, quand il existe.
- **FR-010**: Les compteurs du club MUST compter un résultat de relais attribué **une seule fois**, quel que soit le nombre d'équipiers adhérents.
- **FR-011**: Les compteurs individuels (podiums, victoires, top 10) d'un athlète MUST exclure les résultats de relais. Ces résultats restent affichés, avec leur rang, dans sa liste de résultats. Un compteur « relais » séparé est une évolution possible, hors périmètre.
- **FR-012**: L'affichage des résultats de relais non attribués, les épreuves individuelles et les réponses publiques existantes de l'API MUST rester inchangés pour leurs consommateurs actuels. Seule exception voulue : FR-011 s'applique à **tous** les résultats de relais, attribués ou non, y compris ceux déjà publiés une ligne par équipier. Les compteurs individuels des athlètes concernés baissent donc d'autant.
- **FR-013**: La commande MUST n'être proposée qu'aux détenteurs du pouvoir de rattachement, et le serveur MUST refuser la demande à tout autre appelant.

### Key Entities

- **Résultat de relais** : le temps, le rang et l'épreuve d'une équipe. Il peut porter le nom d'équipe publié par le chronométreur.
- **Équipier** : un athlète rattaché à un résultat de relais. Un résultat de relais attribué a de 2 à 8 équipiers.
- **Fiche d'équipe (athlète fictif)** : une fiche créée à l'import au nom de l'équipe. Elle disparaît quand elle ne porte plus aucun résultat.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Pour les deux cas signalés (#889, fiches 102324 et 39426), le résultat de relais apparaît sur la fiche de chaque équipier après un seul geste d'attribution.
- **SC-002**: Un administrateur attribue un relais à deux équipiers en moins d'une minute, depuis la fiche de l'équipe.
- **SC-003**: Zéro fiche d'équipe vide ne subsiste après une attribution.
- **SC-004**: Les compteurs de podiums du club restent identiques avant et après l'attribution d'un relais à plusieurs adhérents (aucun double compte).
- **SC-005**: Aucun changement observable sur les fiches, classements et compteurs des athlètes qui n'ont aucun résultat de relais.

## Assumptions

- Le pouvoir de rattachement des résultats existant (celui de la réattribution) suffit. Aucun nouveau pouvoir n'est créé.
- Le geste vit dans le back-office sur la fiche athlète, comme la réattribution actuelle. L'écran de validation des courses par les bénévoles est hors périmètre.
- 8 équipiers est un plafond large pour les formats rencontrés (duo, relais à 3 ou 4, relais par équipe de club).
- Les temps intermédiaires par relayeur (qui a nagé, qui a couru) sont hors périmètre : le résultat reste celui de l'équipe.
- Les statistiques propres à une participation (écarts, splits) excluent déjà les relais et continuent de le faire.
- Hors périmètre : le découpage automatique des équipes nommées à l'import (#895, qui réutilisera ce mécanisme) et la reprise des relais déjà en base.
- Le choix du modèle (une liaison résultat vers plusieurs athlètes, ou une copie du résultat par équipier comme le fait déjà `runnerbreizh`) est tranché au plan. Il doit tenir FR-001, FR-010 et FR-012.

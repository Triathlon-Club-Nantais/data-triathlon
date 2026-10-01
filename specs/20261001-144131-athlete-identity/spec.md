# Feature Specification: Une identité stable par athlète réel

**Feature Branch**: `epic/1146-athlete-identity`

**Created**: 2026-10-01

**Status**: Draft

**Input**: User description: "Epic #1146 : un athlète réel = une seule fiche, et une fiche = un seul athlète réel, de façon stable face aux imports concurrents, aux graphies des chronométreurs et aux corrections admin. Sous-issues : #907 (clé d'identité normalisée : accents, ponctuation, espaces), #981 (unicité garantie par la base, création idempotente sous concurrence), #908 (inversions nom/prénom, noms concaténés, fusion admin de deux fiches), #900 (une date de naissance posée par un admin ne scinde plus la fiche), #967 (deux dossards sur une même course individuelle ne donnent pas une seule fiche), #896 (un rescrape ne défait plus une réattribution admin), #906 (reprise des données : renormalisation « NOM, Prénom » et fusion des doublons, mode simulation)."

## Contexte mesuré

Mesures en production, lecture seule, 2026-09-24 (détail et requêtes dans les sous-issues) :

| Défaut | Ampleur | Issue |
| --- | --- | --- |
| Même personne, graphie différente (accents, apostrophe, espace, trait d'union) | 1 889 groupes, 1 930 fiches en trop, 7 138 participations réparties, 41 groupes touchant le club | #907 |
| Nom et prénom inversés | 1 296 paires (2 533 fiches), 10 paires seulement sur une même course | #908 |
| Nom complet sans prénom, avec un jumeau découpé | 3 563 fiches | #908 |
| Format « NOM, Prénom » mal découpé (découpage corrigé à la source par #1006, données non reprises) | ~6 381 fiches, ~2 951 paires de doublons exacts, 51 fiches touchant le club | #906 |
| Homonymes fusionnés sur une même fiche (plusieurs dossards sur une épreuve individuelle) | 58 fiches au minimum, 123 participations | #967 |
| Doublons créés par deux imports simultanés | 0 aujourd'hui (défaut latent, reproduit à 100 % en test) | #981 |
| Date de naissance posée par un admin | la fiche corrigée est vidée au prochain import | #900 |
| Réattribution admin d'un résultat | annulée en silence (avec dossard) ou résultat dupliqué (sans dossard) au rescrape | #896 |

Aucune source ne fournit de date de naissance : sans elle, deux homonymes exacts qui n'ont jamais couru la même épreuve restent indiscernables. C'est une limite assumée.

## Clarifications

### Session 2026-10-01

- Q: Que fait l'import d'une seconde ligne de même identité avec un autre dossard sur une même épreuve individuelle ? → A: Il crée automatiquement une fiche d'homonyme distinguée. Le cas n'ouvre une revue admin que s'il touche le club ; hors club, la mention au rapport d'import suffit.
- Q: Une nouvelle épreuve qui reprend la graphie d'une fiche absorbée par une fusion rejoint-elle la fiche conservée ? → A: Oui, la fusion mémorise l'identité absorbée comme variante de la fiche conservée.
- Q: Quelles paires inversées ou concaténées existantes la reprise fusionne-t-elle sans intervention ? → A: Celles dont les deux fiches ont le même club ou le même genre et ne figurent jamais sur une même épreuve ; les autres passent en revue.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Une graphie différente ne crée plus de fiche (Priority: P1)

Un chronométreur écrit « LETORT Leo » là où un autre écrivait « LETORT Léo », « LEGLOANIC » pour « LE GLOANIC », « L APPARTIEN » pour « L'APPARTIEN », ou publie « Moriarty Alexander » pour « ALEXANDER Moriarty ». À l'import, le résultat rejoint la fiche existante de la personne au lieu d'en créer une seconde. Son palmarès, sa progression et ses compteurs de saison restent entiers.

**Why this priority**: c'est la source principale de fiches scindées (plusieurs milliers) et elle s'aggrave à chaque import. Sans elle, toute reprise des données serait à refaire au prochain import.

**Independent Test**: importer une épreuve contenant une personne connue sous une autre graphie (accent, ponctuation, espace, inversion, nom concaténé), puis vérifier qu'aucune fiche n'a été créée et que le résultat figure sur la fiche existante.

**Acceptance Scenarios**:

1. **Given** une fiche « LETORT Léo », **When** une épreuve importée contient « LETORT Leo », **Then** le résultat est rattaché à la fiche existante et le nombre de fiches ne change pas.
2. **Given** les fiches « LE GLOANIC Fabien » et « L'APPARTIEN Marie », **When** une épreuve contient « LEGLOANIC Fabien » et « L APPARTIEN Marie », **Then** chaque résultat rejoint la fiche existante correspondante.
3. **Given** une fiche « ALEXANDER Moriarty » et aucune fiche « MORIARTY Alexander », **When** une épreuve contient « MORIARTY Alexander », **Then** le résultat rejoint la fiche « ALEXANDER Moriarty ».
4. **Given** une fiche « DUPONT Jean », **When** une épreuve contient un nom seul « DUPONT JEAN » sans prénom, **Then** le résultat rejoint la fiche « DUPONT Jean ».
5. **Given** les fiches factices « CIC 7 » et « CIC 9 », **When** une épreuve les contient à nouveau, **Then** elles restent deux fiches distinctes (les chiffres comptent dans l'identité).
6. **Given** une graphie différente d'une fiche **déjà présente sur la même épreuve individuelle avec un autre dossard**, **When** l'import la rencontre, **Then** elle n'est pas rattachée à cette fiche (règle de la story 4).

---

### User Story 2 - Une correction d'administrateur survit aux imports (Priority: P1)

Un administrateur corrige une fiche (il pose une date de naissance, change le nom) ou réattribue un résultat à une autre fiche. Un rescrape de l'épreuve, unitaire ou en lot, puis l'import d'une nouvelle épreuve où la personne figure, conservent ces corrections : aucune fiche n'est vidée, aucun résultat n'est dupliqué ni rendu à l'ancienne fiche.

**Why this priority**: aujourd'hui une correction est défaite en silence. Le geste de fusion (story 5) et la reprise (story 6) seraient eux-mêmes défaits par le premier rescrape sans cette garantie.

**Independent Test**: importer une épreuve, poser une date de naissance sur une fiche et réattribuer un résultat (avec et sans dossard), rescraper l'épreuve, importer une nouvelle épreuve contenant la personne ; vérifier l'état des fiches.

**Acceptance Scenarios**:

1. **Given** une fiche dont un admin a posé la date de naissance, **When** l'épreuve est rescrapée puis une nouvelle épreuve contenant la personne est importée, **Then** la fiche garde toutes ses participations, gagne la nouvelle, et aucune fiche sans date de naissance n'est créée.
2. **Given** un résultat **avec dossard** réattribué par un admin de la fiche A vers la fiche B, **When** l'épreuve est rescrapée, **Then** le résultat reste sur B.
3. **Given** un résultat **sans dossard** réattribué de A vers B, **When** l'épreuve est rescrapée, **Then** le résultat reste sur B, n'existe qu'une fois, et la fiche A, si elle a été recréée vide au passage, est purgée.
4. **Given** un résultat jamais corrigé par un admin, **When** l'épreuve est rescrapée avec une graphie corrigée par le chronométreur, **Then** il est réconcilié comme aujourd'hui.

---

### User Story 3 - Deux imports simultanés ne créent jamais deux fiches (Priority: P2)

Deux épreuves de chronométreurs différents, importées en même temps (import en lot parallèle ou deux imports web), contiennent la même personne encore inconnue. À la fin, elle n'a qu'une fiche, qui porte les deux résultats.

**Why this priority**: le défaut est latent (0 cas en production) mais certain sous charge, et la règle d'identité des stories 1 et 4 n'a de valeur que si elle est garantie à l'écriture.

**Independent Test**: lancer en parallèle deux imports partageant des personnes inconnues, plusieurs fois de suite, et compter les fiches.

**Acceptance Scenarios**:

1. **Given** deux imports simultanés partageant 300 personnes inconnues, **When** ils se terminent, **Then** il existe exactement 300 fiches pour ces personnes, chacune avec ses deux résultats, et aucun import n'échoue de ce fait.
2. **Given** deux imports simultanés où la même personne apparaît sous deux graphies équivalentes au sens de la story 1, **When** ils se terminent, **Then** elle n'a qu'une fiche.
3. **Given** l'environnement de développement local, **When** on importe une épreuve, **Then** l'import fonctionne comme en production (hors garantie de concurrence).

---

### User Story 4 - Deux homonymes sur une même épreuve gardent deux fiches (Priority: P2)

Deux coureurs homonymes prennent le départ d'une même épreuve individuelle avec deux dossards différents. Ils ne sont pas fusionnés sur une seule fiche ; le cas est signalé à l'administrateur. Les 58 fiches qui mêlent déjà plusieurs personnes sont exposées en revue pour être séparées.

**Why this priority**: c'est le défaut inverse des stories 1 à 3 (une fiche pour plusieurs personnes). Il touche peu de fiches, mais un profil public qui mélange les résultats de deux personnes (catégories des deux sexes, deux temps sur la même course) est visiblement faux.

**Independent Test**: importer une épreuve individuelle contenant deux lignes « MARTIN Thomas » aux dossards différents ; vérifier qu'elles ne portent pas la même fiche et que le conflit est signalé.

**Acceptance Scenarios**:

1. **Given** une épreuve individuelle avec deux lignes de même identité et des dossards distincts, **When** elle est importée, **Then** la seconde ligne crée automatiquement une fiche d'homonyme distinguée, et le conflit figure dans le rapport de l'import.
2. **Given** le cas du scénario 1 où l'une des lignes ou la fiche existante relève du club, **When** l'import se termine, **Then** le cas figure aussi en revue admin, pour vérifier que le membre a gardé la bonne fiche.
3. **Given** le cas du scénario 1 où aucune des deux personnes ne relève du club, **When** l'import se termine, **Then** aucun cas de revue n'est ouvert : la fiche distinguée et la mention au rapport suffisent.
4. **Given** une épreuve **en relais** où une même personne apparaît plusieurs fois, **When** elle est importée, **Then** le comportement actuel est conservé (aucune séparation).
5. **Given** les fiches existantes portant plusieurs dossards sur une même épreuve individuelle et relevant du club, **When** un admin ouvre la revue, **Then** chacune y figure avec ses participations en conflit (épreuve, dossard, temps, catégorie), et il peut les séparer avec les gestes existants de réattribution. Les fiches hors club ne sont listées que dans le rapport de reprise.
6. **Given** une fiche d'homonyme distinguée, **When** une nouvelle épreuve contenant ce nom est importée sans conflit de dossard, **Then** le résultat rejoint la fiche principale du nom, jamais la fiche d'homonyme, qui ne reçoit de résultats que par geste admin.

---

### User Story 5 - Un administrateur fusionne deux fiches d'une même personne (Priority: P2)

Pour un doublon que l'import ne sait pas résoudre (faute de frappe, prénom tronqué, cas laissé en revue), un administrateur ouvre une fiche, désigne l'autre fiche de la même personne et les fusionne. Tout ce qui appartenait à la fiche absorbée passe sur la fiche conservée, et la fiche absorbée disparaît.

**Why this priority**: aucun outil ne permet aujourd'hui de corriger un doublon (renommer la fiche fautive vers l'identité correcte est refusé). La reprise automatique (story 6) laisse des cas ambigus que seul ce geste règle.

**Independent Test**: fusionner deux fiches portant chacune des résultats, une validation de saison et un crédit bénévole ; vérifier la fiche conservée, la disparition de l'autre et le journal.

**Acceptance Scenarios**:

1. **Given** deux fiches A (conservée) et B (absorbée), **When** l'admin les fusionne, **Then** les résultats, les rattachements d'équipier de relais, les crédits bénévoles, les validations de saison et le lien de compte membre de B passent sur A, et B n'existe plus.
2. **Given** B a le club verrouillé et pas A, **When** la fusion est faite, **Then** A hérite du club verrouillé de B.
3. **Given** A et B portent chacune une validation pour la même saison, **When** la fusion est faite, **Then** une seule validation subsiste pour cette saison, sans perte de l'information de validation.
4. **Given** la fusion faite, **When** on consulte le journal d'administration, **Then** le geste y figure une fois, avec les deux fiches et le décompte de ce qui a été déplacé.
5. **Given** la fusion faite, **When** l'épreuve d'origine d'un résultat de B est rescrapée, **Then** le résultat reste sur A et B n'est pas recréée.
6. **Given** la fusion faite, **When** une **nouvelle** épreuve contient la graphie exacte de B, **Then** le résultat rejoint A : la fusion mémorise l'identité de B comme variante de A, et l'import la résout comme l'identité de A (règle de la story 4 comprise).
7. **Given** un administrateur sans le pouvoir d'édition des athlètes, **When** il consulte une fiche, **Then** aucune commande de fusion ne lui est proposée.

---

### User Story 6 - Reprise des doublons existants, simulée avant d'être appliquée (Priority: P3)

Un exploitant lance la reprise des données de production : renormalisation des noms « NOM, Prénom » mal découpés, puis fusion des doublons existants. Il la lance d'abord en simulation, lit le rapport de ce qui serait fait, puis l'applique. Les cas ambigus ne sont pas fusionnés automatiquement : ils sont proposés en revue admin.

**Why this priority**: elle corrige le stock (plusieurs milliers de fiches), mais n'a de sens qu'une fois les stories 1 à 5 livrées, sans quoi le stock se reconstitue ou la fusion est défaite.

**Independent Test**: sur une copie de données contenant chaque famille de doublon, lancer la simulation, vérifier que rien n'a changé et que le rapport liste chaque fusion prévue ; appliquer, vérifier le résultat et le journal.

**Acceptance Scenarios**:

1. **Given** des fiches « JUMEAUX, ADRIEN » (prénom vide), « HOFMANN, » / « Patrick » et « Rose » / « Courjon, » (inversée), **When** la reprise est appliquée, **Then** elles deviennent « JUMEAUX ADRIEN » (nom JUMEAUX, prénom ADRIEN), « HOFMANN Patrick » et « COURJON Rose » (nom et prénom à leur place, virgule retirée), puis rejoignent leur jumeau s'il existe.
2. **Given** un groupe de fiches de même identité normalisée (story 1), **When** la reprise est appliquée, **Then** elles sont fusionnées en une seule, selon les règles de la story 5.
3. **Given** un groupe dont deux fiches portent des dossards distincts sur une même épreuve individuelle (8 groupes mesurés), **When** la reprise tourne, **Then** il n'est pas fusionné et figure en revue manuelle.
4. **Given** les paires inversées ou concaténées existantes, **When** la reprise tourne, **Then** une paire est fusionnée automatiquement quand ses deux fiches ont le même club (renseigné des deux côtés) ou le même genre (renseigné des deux côtés) et ne figurent jamais sur une même épreuve ; les autres paires sont laissées en revue.
5. **Given** la reprise lancée en simulation, **When** elle se termine, **Then** aucune donnée n'a changé et le rapport donne, par famille, le nombre de fiches renormalisées, de fusions prévues et de cas laissés en revue, avec les identifiants concernés.
6. **Given** la reprise appliquée, **When** on la relance, **Then** elle ne trouve plus rien à faire (idempotence).
7. **Given** une fiche factice (« ?DOSSARD #n », « Anonyme … », équipe numérotée, identité masquée), **When** la reprise tourne, **Then** elle n'est ni renormalisée ni fusionnée.

---

### Edge Cases

- Une graphie normalisée vide (nom réduit à de la ponctuation) : la ligne n'est jamais rattachée à une autre fiche à identité vide. Sans dossard, elle est écartée et comptée au rapport, comme un nom masqué (#897) : rien de stable ne permettrait de la retrouver au rescrape. Avec dossard, elle crée sa propre fiche, retrouvée ensuite par le dossard.
- Une inversion qui est un vrai homonyme (« MARTIN Thomas » et « THOMAS Martin ») : à l'import, l'inversion n'est tentée que si l'identité directe ne correspond à aucune fiche ; si elle correspond à une fiche déjà présente sur la même épreuve individuelle, la règle de la story 4 prime.
- Un nom concaténé dont plusieurs découpages correspondent à des fiches différentes : aucun rattachement automatique, une fiche est créée et le cas est signalé.
- Plusieurs fiches répondent à la même identité (fiche principale et fiches d'homonymes distinguées) : l'import choisit toujours la fiche principale.
- Deux fiches à fusionner liées chacune à un compte membre différent : la fusion est refusée avec un message explicite.
- Deux fiches à fusionner qui portent des dossards distincts sur une même épreuve individuelle : la fusion est refusée (ce sont deux personnes), l'admin doit d'abord séparer les résultats.
- Fusion d'une fiche avec elle-même, ou avec une fiche supprimée entre-temps : refusée sans effet.
- Un renommage admin qui ferait coïncider une fiche avec l'identité d'une autre : l'admin est orienté vers la fusion au lieu d'une erreur sèche.
- Une fusion pendant un import qui touche l'une des deux fiches : l'un des deux gestes attend l'autre ; aucun résultat n'est perdu ni rattaché à une fiche supprimée.
- La reprise interrompue en cours de route : relancée, elle reprend sans doubler les fusions déjà faites.

## Requirements *(mandatory)*

### Functional Requirements

**Identité et résolution à l'import**

- **FR-001**: L'identité d'une fiche MUST être comparée sous une forme normalisée : casse ignorée, accents retirés, seuls les lettres et les chiffres conservés, pour le nom comme pour le prénom.
- **FR-002**: La même forme normalisée MUST être utilisée par tous les chemins qui cherchent ou créent une fiche (import unitaire, import en lot, édition admin, reprise).
- **FR-003**: Quand l'identité directe ne correspond à aucune fiche, l'import MUST tenter l'identité inversée (prénom, nom) avant de créer une fiche.
- **FR-004**: Quand le prénom est vide et que le nom compte plusieurs mots, l'import MUST tenter chaque découpage du nom contre les fiches existantes ; il ne rattache que si un seul découpage correspond à une seule fiche.
- **FR-005**: L'import MUST retrouver une fiche quelle que soit sa date de naissance ; une date posée par un admin ne change pas l'identité de la fiche.
- **FR-006**: Une fiche principale MUST exister au plus une fois par identité normalisée, garantie par la base de données, y compris sous imports concurrents.
- **FR-007**: La création d'une fiche par l'import MUST être idempotente : quand deux imports simultanés créent la même identité, ils aboutissent à la même fiche sans échec visible.
- **FR-008**: Une ligne d'une épreuve individuelle MUST NOT être rattachée à une fiche qui porte déjà, sur cette même épreuve, une participation d'un autre dossard.
- **FR-009**: Dans le cas de FR-008, le système MUST créer une fiche d'homonyme distinguée et mentionner le conflit dans le rapport de l'import ; il MUST ouvrir un cas de revue admin seulement si l'une des deux personnes relève du club.
- **FR-010**: Les épreuves en relais MUST conserver leur comportement actuel vis-à-vis de FR-008.

**Protection des corrections admin**

- **FR-011**: Une participation réattribuée par un admin MUST rester sur la fiche choisie à chaque rescrape de l'épreuve, avec ou sans dossard.
- **FR-012**: Le système MUST conserver, pour chaque participation importée, de quoi retrouver la ligne de la source qui l'a produite, indépendamment de la fiche à laquelle elle est rattachée, afin d'apparier un rescrape sans dossard.
- **FR-013**: Un rescrape MUST NOT créer de doublon d'une participation réattribuée ; une fiche recréée vide au passage MUST être purgée comme orpheline.
- **FR-014**: Une participation jamais corrigée MUST continuer d'être réconciliée comme aujourd'hui.

**Fusion admin**

- **FR-015**: Un admin disposant du pouvoir d'édition des athlètes MUST pouvoir fusionner deux fiches depuis l'interface, en désignant la fiche conservée.
- **FR-016**: La fusion MUST reporter sur la fiche conservée toutes les références de la fiche absorbée : participations, rattachements d'équipier de relais, crédits bénévoles, validations de saison, lien de compte membre.
- **FR-017**: La fusion MUST conserver le club verrouillé s'il existe sur l'une des deux fiches, et dédoublonner les validations d'une même saison.
- **FR-018**: La fusion MUST être refusée si les deux fiches sont liées à deux comptes membres différents, ou si elles portent des dossards distincts sur une même épreuve individuelle.
- **FR-019**: La fusion MUST être atomique (tout ou rien) et journalisée une fois dans le journal d'administration, avec les deux fiches et le décompte des éléments déplacés.
- **FR-020**: Un renommage admin qui ferait coïncider deux identités MUST proposer la fusion au lieu d'un refus sans issue.
- **FR-021**: Une fusion MUST résister au rescrape (FR-011 à FR-013 s'appliquent aux participations déplacées).
- **FR-021b**: Une fusion MUST mémoriser l'identité de la fiche absorbée comme variante de la fiche conservée ; l'import MUST résoudre une variante comme l'identité de sa fiche, sous les mêmes règles (FR-006 à FR-010). Une variante MUST NOT appartenir à deux fiches.

**Revue**

- **FR-022**: Le système MUST exposer aux admins une revue des cas d'identité à trancher : fiches du club portant plusieurs dossards sur une même épreuve individuelle, doublons probables que la reprise n'a pas fusionnés, conflits d'homonymes touchant le club signalés par l'import.
- **FR-023**: Chaque cas de revue MUST montrer les éléments de décision : identités, clubs, genre, catégories, épreuves et dossards en commun ou en conflit.

**Reprise des données**

- **FR-024**: La reprise MUST offrir un mode simulation qui ne modifie rien et rapporte, par famille de défaut, les renormalisations et fusions prévues et les cas laissés en revue, avec les identifiants.
- **FR-025**: La reprise MUST renormaliser les noms au format « NOM, Prénom » mal découpés (prénom vide, virgule en fin de nom, nom et prénom inversés), en coupant sur la première virgule.
- **FR-026**: La reprise MUST fusionner les groupes de fiches de même identité normalisée selon les règles de la fusion admin, sauf les groupes qui violeraient FR-018, laissés en revue.
- **FR-027**: La reprise MUST fusionner automatiquement une paire inversée ou concaténée existante quand ses deux fiches ont le même club ou le même genre, renseigné des deux côtés et égal après normalisation, et ne figurent jamais sur une même épreuve, et laisser les autres en revue.
- **FR-028**: La reprise MUST exclure les fiches factices (bouche-trous de dossard, anonymes, équipes numérotées, identités masquées).
- **FR-029**: La reprise MUST être idempotente et reprenable après interruption, et journaliser chaque fusion appliquée.
- **FR-030**: La reprise MUST signaler les fiches datées par un admin qui ont déjà un homonyme non daté (scission #900 déjà survenue) et les fusionner selon FR-026.

### Key Entities

- **Athlète (fiche)** : une personne physique. Porte un nom et un prénom tels qu'affichés, une identité normalisée qui sert à la comparer, éventuellement une date de naissance, un club (verrouillable), un statut « principale » ou « homonyme distinguée » pour son identité, et les variantes d'identité mémorisées par les fusions qu'elle a absorbées.
- **Participation** : un résultat sur une épreuve, rattaché à une fiche. Porte désormais l'empreinte de la ligne source qui l'a produite (identité scrapée d'origine, dossard) et l'indication qu'un admin a choisi sa fiche.
- **Fusion** : geste admin ou de reprise qui absorbe une fiche dans une autre. Journalisé (auteur, date, fiches, éléments déplacés).
- **Cas de revue d'identité** : un doublon probable ou un conflit d'homonymes à trancher par un admin, avec ses éléments de décision et son issue (fusionné, séparé, écarté).
- **Rapport de reprise** : le résultat d'une simulation ou d'une application de la reprise, par famille de défaut.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Après la reprise, les 1 930 fiches en trop dues aux seuls accents, ponctuation et espaces (mesure du 2026-09-24) tombent à 0, hors groupes laissés en revue au titre de FR-018.
- **SC-002**: Après la reprise, plus aucune fiche ne porte une virgule dans son nom ou son prénom, hors fiches factices et noms d'équipe.
- **SC-003**: Les 41 groupes de doublons touchant le club et les 51 fiches « NOM, Prénom » touchant le club sont tous résolus (fusionnés ou tranchés en revue) : chaque membre concerné retrouve un compteur de saison complet.
- **SC-004**: Réimporter une épreuve déjà importée, ou importer une épreuve contenant des personnes connues sous une graphie équivalente, crée 0 fiche nouvelle pour ces personnes.
- **SC-005**: Sur 10 essais d'imports simultanés partageant 300 personnes inconnues, 0 doublon.
- **SC-006**: 100 % des corrections admin (date de naissance, réattribution, fusion) survivent à un rescrape de l'épreuve et à l'import d'une nouvelle épreuve.
- **SC-007**: Aucun import ne rattache plus deux dossards distincts d'une même épreuve individuelle à une même fiche ; parmi les fiches existantes dans ce cas, 100 % de celles qui relèvent du club figurent en revue.
- **SC-008**: Un admin fusionne deux fiches en moins d'une minute, sans intervention technique.
- **SC-009**: La simulation de reprise annonce exactement ce que l'application fait ensuite (écart nul entre les deux rapports sur les mêmes données).

## Assumptions

- Aucune source ne fournit de date de naissance ; deux homonymes exacts qui n'ont jamais couru la même épreuve restent sur une seule fiche (limite connue, hors périmètre).
- Le découpage « NOM, Prénom » à l'import est déjà corrigé (#1006) ; seule la reprise du stock reste à faire pour #906.
- Le rapprochement flou (fautes de frappe, prénoms composés tronqués) n'est pas automatisé : il passe par la fusion admin.
- Les fiches factices et les noms d'équipe avec virgule (#63, #895, #710) sont hors périmètre.
- La reprise des corrections admin déjà écrasées par des rescrapes passés est hors périmètre.
- La correction de la saisie à la source chez les fournisseurs est hors périmètre.
- Le pouvoir d'édition des athlètes existant suffit pour fusionner ; aucun nouveau rôle n'est créé.
- La reprise est lancée par un exploitant depuis la ligne de commande de batch, contre la base de production, simulation d'abord.
- Les sous-issues sont livrées dans la branche d'intégration de l'epic, chacune par sa propre PR, dans l'ordre des priorités ci-dessus.

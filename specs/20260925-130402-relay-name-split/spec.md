# Feature Specification: Découper à l'import les relais qui nomment leurs équipiers

**Feature Branch**: `895-relay-name-split`

**Created**: 2026-09-25

**Status**: Draft

**Input**: User description: "Issue #895 (sous-issue de l'epic #889, dépend de #894 déjà mergée dans epic/889-relais) : quand la ligne de résultat d'un relais nomme ses équipiers (« DUPONT Jean / MARTIN Paul », « A & B »), l'import crée un athlète au nom de l'équipe et le résultat n'apparaît sur le profil d'aucun équipier. Demande : découper un nom d'équipe qui nomme ses équipiers et rattacher chacun au résultat via le mécanisme de #894 ; ne pas découper un nom de groupe ; jamais hors relais (cf. #63) ; couverture par fournisseur avec des fixtures réelles. Hors périmètre : le modèle et l'attribution manuelle (#894), la reprise des relais déjà importés."

**Sondage de référence** : `docs/superpowers/specs/2026-09-25-relais-noms-equipiers-sondage.md` (base de dev, 1 041 résultats de relais, et fixtures). Il prime sur cette spec en cas de divergence.

## Clarifications

### Session 2026-09-25

- Q : une ligne qui ne publie que des prénoms (« LES BARBAPAPAS | Alex et Margot », 497 lignes breizhchrono) est-elle découpée ? → R : non. Elle est traitée comme un nom de groupe et reste attribuable à la main.
- Q : que faire quand la frontière entre nom et prénom d'un équipier est indécidable (« LE BRAS LUC », tout en majuscules) ? → R : tout ou rien par ligne. Un seul équipier ambigu suffit à laisser la ligne entière non découpée.
- Q : un relais déjà importé et encore porté par une fiche d'équipe est-il découpé quand son épreuve est re-scrapée ? → R : oui, avec la même règle qu'à l'import. Aucune campagne de reprise en masse n'est lancée.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un relais aux équipiers nommés apparaît sur la fiche de chacun dès l'import (Priority: P1)

Un adhérent court un relais en duo. Le chronométreur publie la ligne « DUPONT Jean / MARTIN Paul ». Quand l'épreuve est importée, le résultat apparaît directement sur la fiche de Jean DUPONT et sur celle de Paul MARTIN, sans intervention d'un administrateur. Aucune fiche « DUPONT Jean / MARTIN Paul » n'est créée.

**Why this priority**: c'est le défaut signalé (#889, fiche 102324). Sans découpage automatique, chaque relais nommé exige un geste manuel d'attribution (#894).

**Independent Test**: importer une épreuve de relais dont une ligne nomme deux équipiers en entier. Vérifier que le résultat figure sur deux fiches de personnes et qu'aucune fiche ne porte le nom de l'équipe.

**Acceptance Scenarios**:

1. **Given** une épreuve de relais dont une ligne publie « NOM1/NOM2 » et « Prénom1/Prénom2 » (forme timepulse), **When** l'épreuve est importée, **Then** le résultat est rattaché à NOM1 Prénom1 et NOM2 Prénom2, dans cet ordre, et aucune fiche d'équipe n'est créée.
2. **Given** une ligne « NOM1 PRÉNOM1 / NOM2 PRÉNOM2 » tout en majuscules (forme mesurée chez klikego, oktime et chronoplace), **When** l'épreuve est importée, **Then** chaque équipier est créé ou retrouvé avec le bon nom et le bon prénom.
3. **Given** un équipier dont une fiche de même nom et prénom existe déjà, **When** l'épreuve est importée, **Then** le résultat est rattaché à cette fiche existante et aucun doublon n'est créé.
4. **Given** un relais découpé à l'import, **When** on consulte le résultat, **Then** le nom d'équipe publié par le chronométreur reste visible.

---

### User Story 2 - Un nom de groupe reste une fiche d'équipe attribuable à la main (Priority: P1)

Une équipe s'inscrit sous « OGGY ET LES CAFARDES », « TIC & TAC » ou « LES BARBAPAPAS | Alex et Margot ». Rien dans la ligne ne permet de connaître le nom et le prénom de chaque équipier. L'import laisse le résultat sur une fiche d'équipe, comme aujourd'hui, et un administrateur peut l'attribuer à la main (#894).

**Why this priority**: un découpage à tort fabrique de fausses personnes (« OGGY », « LES CAFARDES »), plus coûteuses à nettoyer qu'une fiche d'équipe. C'est la garde qui rend la story 1 sûre, d'où la même priorité.

**Independent Test**: importer une épreuve de relais qui mêle noms de groupe, prénoms seuls et une ligne ambiguë. Vérifier qu'aucune de ces lignes n'a été découpée.

**Acceptance Scenarios**:

1. **Given** une ligne de relais qui porte un nom de groupe (avec ou sans « et », « & », « / »), **When** l'épreuve est importée, **Then** la ligne n'est pas découpée.
2. **Given** une ligne de relais qui ne publie que des prénoms, **When** l'épreuve est importée, **Then** la ligne n'est pas découpée.
3. **Given** une ligne « NOM1 PRÉNOM1 / LE BRAS LUC » dont un seul équipier a une frontière nom et prénom indécidable, **When** l'épreuve est importée, **Then** la ligne entière n'est pas découpée.
4. **Given** une ligne non découpée, **When** un administrateur l'attribue à la main, **Then** le mécanisme de #894 fonctionne comme avant.

---

### User Story 3 - Un nom de personne hors relais n'est jamais cassé (Priority: P1)

Sur une épreuve individuelle, un coureur porte un nom composé (« DUBOIS-HERRY », « Marie-Claire LE GALL »), ou un binôme s'est inscrit sous une seule ligne (« CHAIGNEAU BENJAMIN / LENOIR-LEDOUX CHRISTELLE »). L'import ne découpe jamais ces lignes : il les traite exactement comme aujourd'hui.

**Why this priority**: c'est l'invariant de #63. Un découpage hors relais casserait des identités légitimes sur l'ensemble des épreuves individuelles.

**Independent Test**: importer une épreuve individuelle qui contient des noms avec « / », « - », « & » et « et ». Vérifier que les fiches créées sont identiques à celles d'avant la fonctionnalité.

**Acceptance Scenarios**:

1. **Given** une épreuve et une ligne qui ne sont pas des relais, **When** l'épreuve est importée, **Then** aucun nom n'est découpé en équipiers, quel que soit le séparateur présent.
2. **Given** un relais dont un équipier a un nom composé (« PINSON/ROCHEFORT-CUNIN | Eric/Emmanuel »), **When** l'épreuve est importée, **Then** le tiret reste dans le nom de l'équipier (« ROCHEFORT-CUNIN Emmanuel »).

---

### User Story 4 - Un rescrape découpe les relais encore portés par une fiche d'équipe (Priority: P2)

Une épreuve importée avant la fonctionnalité est re-scrapée. Ses relais aux équipiers nommés, encore portés par une fiche « A / B », sont découpés selon la même règle. La fiche d'équipe vidée disparaît. Une composition déjà posée à la main n'est jamais modifiée.

**Why this priority**: permet de corriger l'existant épreuve par épreuve, sans campagne de reprise. Secondaire par rapport au comportement à l'import.

**Independent Test**: sur une épreuve déjà en base avec une fiche d'équipe « NOM1 PRÉNOM1 / NOM2 PRÉNOM2 », relancer le scrape. Vérifier le rattachement aux deux équipiers et la disparition de la fiche d'équipe. Relancer une seconde fois : aucun changement.

**Acceptance Scenarios**:

1. **Given** un relais importé avant la fonctionnalité et porté par une fiche d'équipe aux équipiers nommés, **When** son épreuve est re-scrapée, **Then** le résultat est rattaché aux équipiers et la fiche d'équipe, si elle ne porte plus aucun résultat, est supprimée.
2. **Given** un relais dont un administrateur a posé la composition à la main (#894), **When** son épreuve est re-scrapée, **Then** la composition reste exactement celle posée par l'administrateur.
3. **Given** un relais déjà découpé, **When** son épreuve est re-scrapée une nouvelle fois, **Then** rien ne change (ni doublon de résultat, ni nouvelle fiche).

---

### Edge Cases

- Nombre d'équipiers hors de la plage admise par #894 (moins de 2 ou plus de 8) : la ligne n'est pas découpée.
- Listes parallèles de longueurs différentes (« A/B/C | Jean/Paul ») : la ligne n'est pas découpée.
- Espaces irréguliers autour du séparateur (« HUREAU /HUREAU/PERDREAU | Régis /Marianne/Jean-Sebastien ») : ils sont ignorés et les noms nettoyés.
- Marqueur parasite ajouté par la source (le « . » final de klikego) : il ne fait partie d'aucun nom.
- Deux équipiers de même nom de famille et de prénoms différents (familles, 11 lignes timepulse) : deux équipiers distincts.
- Même personne répétée deux fois dans une ligne : la ligne n'est pas découpée.
- Initiales seules (« S. D. ») : la ligne n'est pas découpée.
- Un équipier porte déjà un autre résultat sur la même épreuve : la ligne n'est pas découpée, et l'import de l'épreuve ne doit pas échouer pour autant.
- Un segment d'une ligne découpée ne porte qu'un seul mot (« DAMIEN/FRANCOIS ») : la ligne n'est pas découpée.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sur un résultat de relais (épreuve ou ligne marquée relais), l'import MUST découper la ligne en équipiers quand elle nomme chacun d'eux par un nom **et** un prénom, et rattacher le résultat à ces équipiers par le mécanisme de #894, dans l'ordre publié.
- **FR-002**: Seul le séparateur « / » MUST déclencher un découpage. « & », « et », « + », la virgule et le tiret n'en déclenchent aucun (sondage : aucune de leurs occurrences en relais ne relie deux noms complets).
- **FR-003**: Une ligne MUST rester non découpée si un seul de ses segments ne permet pas d'établir sans ambiguïté un nom et un prénom : segment d'un seul mot, prénoms seuls, initiales, frontière nom et prénom indécidable. Le découpage est tout ou rien par ligne.
- **FR-004**: Le découpage MUST partir de la valeur publiée, avant toute coupure en nom et prénom. Il lit les listes parallèles de noms et de prénoms position à position, et un équipier écrit tout en majuscules comme « NOM PRÉNOM » (convention mesurée chez klikego, oktime et chronoplace).
- **FR-005**: Un équipier MUST réutiliser la fiche existante de même nom et prénom, selon la même règle d'identité que l'attribution manuelle de #894. Sinon sa fiche est créée.
- **FR-006**: Une ligne découpée MUST ne créer aucune fiche au nom de l'équipe, et MUST conserver le nom d'équipe publié, visible sur le résultat.
- **FR-007**: Un résultat ou une épreuve qui n'est pas un relais MUST être importé exactement comme aujourd'hui, quels que soient les caractères présents dans les noms.
- **FR-008**: Une ligne non découpée MUST être importée comme aujourd'hui (une fiche d'équipe), et rester attribuable à la main par #894.
- **FR-009**: Le rescrape d'une épreuve MUST appliquer la même règle aux relais encore portés par une fiche d'équipe, et purger la fiche d'équipe vidée selon la règle existante. Il MUST ne jamais modifier une composition posée par un administrateur, ni dupliquer un résultat ou une fiche au rescrape suivant.
- **FR-010**: Une ligne dont un équipier porte déjà un autre résultat sur la même épreuve, ou qui répète la même personne, MUST rester non découpée, sans faire échouer l'import de l'épreuve.
- **FR-011**: La couverture de tests MUST s'appuyer sur des lignes réelles, par fournisseur qui publie des relais nommés : timepulse, klikego, oktime et chronoplace (formes mesurées au sondage). Pour raceresult et chronoweb, que l'issue cite mais pour lesquels le sondage ne trouve aucun relais aux équipiers nommés, la couverture porte sur leurs formes réelles de relais (noms de groupe), qui MUST rester non découpées.

### Key Entities

- **Ligne de relais publiée** : le nom (et éventuellement le prénom) que le chronométreur associe à un résultat d'équipe. Elle nomme ses équipiers, ou porte un nom de groupe.
- **Équipier** : une personne identifiée par un nom et un prénom, rattachée au résultat de relais (entité livrée par #894).
- **Fiche d'équipe** : la fiche créée au nom de l'équipe quand la ligne n'est pas découpée. Elle reste attribuable à la main.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur les formes mesurées au sondage, 100 % des lignes de relais aux équipiers nommés sans ambiguïté (180 lignes en base de dev) sont découpées à l'import, et aucune ne crée de fiche d'équipe.
- **SC-002**: Zéro ligne de nom de groupe, de prénoms seuls ou ambiguë n'est découpée (0 fausse personne créée sur les 861 autres lignes de relais mesurées).
- **SC-003**: Zéro nom de personne hors relais n'est modifié : les fiches créées par l'import d'une épreuve individuelle sont identiques avant et après la fonctionnalité.
- **SC-004**: Un second rescrape de la même épreuve ne produit aucun changement (idempotence).
- **SC-005**: Le cas signalé en #889 (fiche 102324, relais « A / B ») s'importe sur la fiche de chacun des deux équipiers sans geste d'administrateur, s'il relève d'une forme découpable.

## Assumptions

- #894 est livrée dans la branche d'epic : l'attribution d'un résultat à 2 à 8 équipiers, la règle d'identité par nom et prénom et la purge des fiches vides sont réutilisées, pas redéfinies.
- Le « A & B » cité par l'issue n'a aucune réalisation mesurée en relais (sondage). Il reste traité comme un nom de groupe. Si une forme réelle apparaît, elle fera l'objet d'une issue avec sa fixture.
- La base de production n'a pas été mesurée (accès refusé pendant le sondage). Les proportions viennent de la base de dev et des fixtures.
- Aucune campagne de reprise en masse : seuls les imports et rescrapes à venir appliquent la règle (issue de suite de l'epic).
- L'appariement au rescrape d'un relais sans dossard (livré par #894, par nom d'équipe) doit rester stable : la forme du nom d'équipe conservée ne doit pas changer d'un scrape à l'autre.
- Les compteurs (podiums de relais hors compteurs individuels, une fois pour le club) suivent la règle de #894, sans changement.

# Research: groupes d'entraînement, inscription d'office, séances récurrentes

## R1. Catégories d'âge FFTri et bascule de saison

- **Decision**: catégorie = f(âge sportif), âge sportif = `année de saison − 1 − année de naissance`, la saison `S` couvrant du 1er novembre `S−1` au 31 octobre `S`. Bornes : moins de 6 ans « Moins de 6 ans », 6-7 Mini-poussin, 8-9 Poussin, 10-11 Pupille, 12-13 Benjamin, 14-15 Minime, 16-17 Cadet, 18-19 Junior, 20 et plus Senior.
- **Rationale**: les règlements d'épreuves FFTri 2026 relevés le 2026-10-10 donnent Mini-poussins 2018-2019, Poussins 2016-2017, Pupilles 2014-2015, Benjamins 2012-2013, Minimes 2010-2011, Cadets 2008-2009, Juniors 2006-2007 : soit un âge compté sur l'année 2025 pour la saison 2026, cohérent avec une saison qui démarre à l'automne de l'année précédente. Ce tableau sert d'oracle aux tests.
- **Point à confirmer**: le mois de bascule (1er novembre retenu) n'a pas été trouvé dans un texte officiel FFTri ; il vit dans une constante unique, signalée `ponytail:` dans le code, à corriger d'une ligne si le club donne une autre date.
- **Alternatives considered**: âge au jour près (refusé : la FFTri catégorise par année de naissance) ; catégorie saisie à la main (refusé : dérive à chaque saison).

## R2. Origine d'une inscription

- **Decision**: une colonne booléenne `added_manually` sur `training_participants` (vraie pour l'ajout individuel, fausse pour l'inscription d'office). L'appartenance d'un participant « par groupe » se recalcule depuis les groupes visés par la séance.
- **Rationale**: FR-005 demande seulement de ne pas désinscrire un jeune ajouté à la main ou couvert par un autre groupe visé ; la seconde condition se vérifie sur les données présentes, sans stocker le groupe d'origine (qui serait faux dès qu'un jeune est couvert par deux groupes).
- **Alternatives considered**: colonne `enrolled_via_group_id` (refusée : une seule origine possible, ambiguë avec deux groupes) ; table d'origines (refusée, YAGNI).

## R3. Synchronisation groupe → séances

- **Decision**: une fonction de service `sync_group_enrolment(db, session)` calcule l'ensemble voulu (membres actifs des groupes visés à la date de la séance) et l'applique à une séance **à venir** (date ≥ aujourd'hui) **dont l'appel n'a pas commencé** (aucun `present` non nul) : ajoute les manquants (`added_manually=False`), retire les inscrits non manuels absents de l'ensemble. Appelée à la création et à la modification d'une séance, et pour chaque séance concernée après un ajout ou un retrait de membre de groupe.
- **Rationale**: une seule règle, écrite une fois, couvre US2.1 à US2.5 et FR-006 ; synchrone, car les volumes sont petits (dizaines de jeunes, dizaines de séances à venir).
- **Alternatives considered**: tâche de fond (refusée, aucun volume ne le justifie) ; inscription figée à la création seule (refusée par US2.5 et FR-006).

## R4. Récurrences

- **Decision**: table `training_recurrences` (jour de semaine 0-6, heure optionnelle, lieu, type, période) ; `training_sessions` gagne `recurrence_id` (nullable) et `detached` (booléen, vrai dès qu'une séance générée est modifiée seule). Création : génère les dates de la période, refus au-delà de 53 occurrences ou si aucune. Modification : sur les séances à venir, non détachées et sans appel commencé, supprime celles hors du nouvel ensemble de dates, met à jour les autres (heure, lieu, type, groupes), crée les dates manquantes, puis resynchronise les inscriptions. Suppression : supprime ces mêmes séances, détache (`recurrence_id = NULL`) les autres.
- **Rationale**: FR-008 à FR-012 sans moteur de récurrence (RRULE) : le club n'a que des créneaux hebdomadaires (hypothèse de la spec).
- **Alternatives considered**: moteur RRULE (`dateutil.rrule`), inutile pour un pas fixe de 7 jours que `timedelta(weeks=1)` couvre ; séances virtuelles calculées à la volée (refusé : l'appel a besoin de lignes réelles).
- **Heure d'été**: les heures sont stockées en heure locale naïve (`Time`), comme les séances existantes ; aucune conversion, l'heure saisie reste l'heure affichée.

## R5. Nommage générique et collision avec `groups`

- **Decision**: tables `training_groups`, `training_group_members`, `training_session_groups`, `training_recurrences`, `training_recurrence_groups`.
- **Rationale**: `groups` existe déjà (groupes d'appartenance RBAC, #197) ; le préfixe `training_` reste générique (jeunes et adultes s'entraînent) et respecte FR-015.

## R6. Purge de rétention (#1158)

- **Decision**: la purge d'un profil retire aussi ses appartenances de groupe, avant le profil, comme elle retire déjà ses inscriptions (`delete_participations_of_profile`).
- **Rationale**: pas d'`ondelete` en base dans ce dépôt (aucun `PRAGMA foreign_keys` côté SQLite) ; la purge doit nettoyer explicitement.

## R7. Coexistence avec #1290

- **Decision**: #1290 (corrections des écrans jeunes, dont `DELETE` d'une séance et le tri du calendrier) est en cours sur une autre branche. L'implémentation de cette feature se fait **après sa fusion**, branche rebasée sur `main`, pour réutiliser la route de suppression et la mise en page corrigée.

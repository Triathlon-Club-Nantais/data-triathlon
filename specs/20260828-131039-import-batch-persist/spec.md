# Feature Specification: Persist par lot pour l'import de résultats

**Feature Branch**: `20260828-131039-import-batch-persist`

**Created**: 2026-08-28

**Status**: Draft

**Input**: User description: "Fix perf(import) issue #706: row-by-row DB round-trips in _Persister.add (backend/app/services/import_service.py) make persist O(n) — 89s in production for 1147 rows vs 2s locally on SQLite. Batch-resolve athlete lookups (one SELECT per course/tranche of 500 instead of per-row), use bulk_insert_mappings for new participations, and load each course's existing participations only once (currently reloaded at both _index_course and finalize()). This is also the likely structural cause of two cascading symptoms: false "Erreur" messages after successful commits, and SSE connections dying without a done/error phase on some imports."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import d'une épreuve volumineuse sans blocage (Priority: P1)

Un membre du bureau colle l'URL de chronométrage d'une épreuve à plusieurs
centaines ou milliers de participants (ex. Trégastel, 1147 lignes). L'import se
termine en quelques secondes au lieu de plus d'une minute, sans que
l'utilisateur se demande si l'application est bloquée.

**Why this priority**: C'est le symptôme mesuré (89 s en production) qui rend
l'outil pénible à utiliser sur toute épreuve de taille significative — c'est la
raison d'être de l'issue.

**Independent Test**: Importer un jeu de résultats scrapé de ~1000+ lignes
réparties sur une ou plusieurs courses (fan-out), et mesurer le temps entre le
déclenchement de l'import et la fin (statut « terminé ») en environnement de
production (latence réseau DB non nulle, ex. Supabase). Le nombre de
requêtes DB émises pendant `_Persister.add`/`finalize` doit être borné par le
nombre de courses/tranches, pas par le nombre de lignes.

**Acceptance Scenarios**:

1. **Given** un scrape de 1147 lignes sur une seule course, **When** l'import
   est lancé, **Then** il se termine avec le même résultat final (comptes
   `imported`/`updated`/`skipped`/`reconciled`, qualité de course, athlètes
   créés/fusionnés) qu'avec l'implémentation actuelle ligne-à-ligne, en un temps
   très inférieur à l'actuel.
2. **Given** un scrape multi-courses (fan-out, plusieurs heats), **When**
   l'import est lancé, **Then** chaque course voit ses participations et son
   rapport qualité calculés correctement, sans mélange entre courses.

---

### User Story 2 - Fin d'import fiable, sans faux message d'erreur (Priority: P2)

Un membre lance un import qui aboutit réellement (toutes les lignes
persistées, transaction commitée), mais voit aujourd'hui parfois un message
« Erreur » trompeur car la transaction traîne assez longtemps pour que la
connexion DB soit recyclée en cours de route. Après le raccourcissement du
temps de persistance, ce faux signal doit disparaître ou devenir marginal.

**Why this priority**: Un message d'erreur après un succès réel casse la
confiance dans l'outil et pousse à ré-importer inutilement — mais c'est un
effet secondaire probable, pas garanti, du correctif de performance : priorité
en dessous du gain de temps lui-même.

**Independent Test**: Reproduire un import de volume comparable à celui qui
déclenchait le faux « Erreur » avant le correctif (voir #704/#705 pour le
contexte des symptômes en cascade) et vérifier qu'il se termine avec un statut
cohérent avec l'état réel en base.

**Acceptance Scenarios**:

1. **Given** un import qui persiste correctement toutes les lignes, **When**
   la transaction est commitée en un temps très inférieur au seuil de recyclage
   de connexion observé en production, **Then** l'utilisateur voit un statut de
   succès cohérent avec l'état réel en base.

---

### User Story 3 - Progression SSE qui va jusqu'au bout (Priority: P3)

Un membre suit la barre de progression d'un import via la connexion SSE.
Aujourd'hui, certains imports longs voient cette connexion mourir sans jamais
atteindre une phase `done` ou `error` (le worker est tenu trop longtemps).
Une fois la persistance raccourcie, la connexion doit atteindre une phase
terminale dans l'immense majorité des cas.

**Why this priority**: Effet secondaire probable du même correctif, mais
symptôme le moins fréquent des trois et déjà couvert séparément (#705) — sa
résolution ici est un bénéfice constaté, pas l'objectif premier de cette
feature.

**Independent Test**: Suivre la connexion SSE d'un import de volume
équivalent à ceux qui expiraient avant le correctif, et vérifier qu'elle émet
bien une phase terminale (`done` ou `error`).

**Acceptance Scenarios**:

1. **Given** un import dont la persistance est désormais bornée dans le temps,
   **When** le client suit la progression en SSE, **Then** la connexion reçoit
   une phase terminale avant tout timeout applicatif.

---

### Edge Cases

- Que se passe-t-il quand une tranche contient des doublons de dossard au sein
  du même scrape (déjà géré aujourd'hui par le comptage `skipped` /
  `_duplicate_bibs`) ? Le comportement doit rester identique après le passage
  en lot.
- Que se passe-t-il quand deux lignes du même scrape désignent le même athlète
  sous des graphies différentes (réconciliation, #66) ? La résolution par lot
  ne doit pas introduire de collision entre deux athlètes distincts résolus
  dans la même tranche avant que l'un des deux soit flushé.
- Que se passe-t-il pour une course qui reçoit zéro nouvelle ligne dans ce
  scrape (toutes déjà connues, aucun changement) ? `finalize()` doit toujours
  produire un rapport qualité et des compteurs corrects sans recharger deux
  fois les participations.
- Que se passe-t-il si le lot d'athlètes à résoudre dépasse la taille d'une
  tranche (> 500 lignes) ? La résolution doit continuer à couvrir l'intégralité
  du lot, pas seulement la première tranche.
- Que se passe-t-il si l'insertion en lot des nouvelles participations échoue
  partiellement (contrainte DB) ? Le comportement d'échec (rollback complet de
  l'import, message d'erreur) doit rester celui du chemin actuel — pas de
  correctif de gestion d'erreurs dans le périmètre de cette feature (couvert
  par #704).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT résoudre les athlètes correspondant aux lignes
  d'un import par lot (une requête couvrant plusieurs lignes, par course ou par
  tranche bornée) plutôt que par un aller-retour DB par ligne, sans changer le
  résultat de la résolution (athlète existant retrouvé, ou créé, selon les
  mêmes règles d'identité nom + prénom + date de naissance qu'aujourd'hui).
- **FR-002**: Le système DOIT persister les nouvelles participations d'un
  import en une opération groupée plutôt qu'un `INSERT` par ligne, sans changer
  les champs persistés par ligne.
- **FR-003**: Le système DOIT charger les participations existantes d'une
  course une seule fois par import, réutilisée aussi bien pour l'indexation en
  cours d'import (`_index_course`) que pour le calcul du rapport qualité en fin
  d'import (`finalize`), au lieu de la recharger aux deux étapes.
- **FR-004**: Le système DOIT produire, pour un même scrape en entrée, des
  compteurs (`imported`, `updated`, `skipped`, `reconciled`, doublons de
  dossard) et un rapport qualité de course strictement identiques à ceux de
  l'implémentation actuelle ligne-à-ligne.
- **FR-005**: Le système DOIT continuer à traiter correctement un import qui
  couvre plusieurs courses dans le même scrape (fan-out multi-heats), en
  gardant l'isolation des lots par course.
- **FR-006**: Le système DOIT réduire le nombre d'allers-retours DB émis
  pendant la persistance d'un import à un ordre de grandeur proportionnel au
  nombre de courses/tranches du scrape, et non plus au nombre de lignes
  importées.

### Key Entities

- **Athlete** : identité résolue par nom + prénom (+ date de naissance quand
  connue) ; la résolution par lot doit retrouver ou créer les mêmes fiches que
  la résolution ligne à ligne actuelle.
- **Participation** : ligne de résultat rattachée à une `Course` et un
  `Athlete` ; les nouvelles lignes d'un scrape doivent être insérées en lot.
- **Course** : unité sur laquelle sont indexées les participations
  existantes (chargées une seule fois) et calculé le rapport qualité en fin
  d'import.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un import de volume comparable à Trégastel 2026 (1147 lignes) se
  termine en production en une fraction du temps actuel (89 s), de l'ordre de
  quelques secondes plutôt qu'une à deux minutes.
- **SC-002**: Le nombre de requêtes DB émises pendant la persistance d'un
  import ne croît plus linéairement avec le nombre de lignes importées.
- **SC-003**: Sur la suite de tests existante couvrant l'import (résolution
  d'athlètes, réconciliation, comptage qualité), 100 % des cas continuent de
  passer sans modification de leurs assertions sur le résultat métier.
- **SC-004**: La fréquence des faux messages « Erreur » après commit réussi et
  des connexions SSE sans phase terminale, mesurée sur des imports de volume
  comparable, diminue par rapport à l'état actuel (mesure de suivi, pas un
  objectif garanti par cette seule feature).

## Assumptions

- Le périmètre du correctif est celui décrit dans l'issue #706 : résolution
  d'athlètes par lot, insertion groupée des nouvelles participations,
  déduplication du rechargement des participations existantes par course.
  La résolution de course (`get_or_create_course`) reste hors périmètre — elle
  n'est pas identifiée comme un goulot dans l'audit source.
- La taille de tranche pour la résolution par lot suit l'ordre de grandeur
  cité dans l'issue (≈500 lignes) ; la valeur exacte est un détail
  d'implémentation tranché en phase de planification, pas un critère
  d'acceptation utilisateur.
- Les symptômes en cascade (faux « Erreur », SSE sans phase terminale) sont
  traités ici comme des bénéfices attendus mais non garantis par ce seul
  correctif — leur résolution complète, si elle s'avère nécessiter davantage,
  relève des issues dédiées #704 et #705.
- L'environnement de mesure de référence pour SC-001 est la production
  (Render → Supabase) citée dans l'issue, pas l'environnement local SQLite où
  le problème n'est pas observable au même degré.

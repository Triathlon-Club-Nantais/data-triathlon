# Implementation Plan: Support de MYLAPS Sporthive comme fournisseur de résultats

**Branch**: `feat-scrapers-supporter-results.sporthive.com-my` | **Date**: 2026-07-29, révisé le 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-sporthive-scraper/spec.md`

**Source de vérité technique**: `docs/superpowers/specs/2026-07-29-sporthive-sondage.md`
— il prime sur ce plan en cas de divergence factuelle.

**Révision du 30/07/2026** : la session de clarification `### Session 2026-07-30`
de la spec a tranché cinq points (granularité de l'échec, statut sans temps,
lieu / pays, course sans classé, import à zéro course). Ils ont produit FR-008a,
FR-008b, FR-008c, FR-014a, FR-022a et SC-008, révisé D4/D5/D6 et ajouté D14/D15
au `research.md`. Ce plan est réaligné sur eux ; aucun ne change la stack, le
périmètre ni le nombre de fichiers touchés.

## Summary

Ajouter `sporthive` au registre des fournisseurs : un module
`backend/app/scrapers/sporthive.py` qui, depuis une URL `sporthive.com`, lit
l'identifiant d'événement, énumère les courses de l'événement et pagine chaque
classement via l'API JSON publique de MYLAPS
(`eventresults-api.speedhive.com/sporthive`), pour rendre une liste de
`ScrapedResult`.

Trois contraintes de la source dictent le design, toutes mesurées au sondage :
la pagination est **plafonnée à 10** par requête (≈ 100 requêtes pour l'épreuve
du Sheet) ; le segment `races/{n}` de l'URL est un **ordinal local** dont l'usage
naïf importerait une épreuve étrangère sans erreur ; et le statut sportif vit
dans `validity`, les deux booléens `dns`/`dsq` étant morts.

S'y ajoute une contrainte de **structure**, issue du cadrage : une URL Sporthive
vaut une épreuve pour l'infra d'import, mais N courses pour la source. Le module
porte donc **deux portées d'échec** — une course fautive est écartée
(`_IncompleteRanking`, type privé, rattrapé par la boucle), l'événement est refusé
(`ValueError` propagée) quand l'invariant d'arrêt tombe ou qu'**aucune** course
n'a pu être lue. C'est ce dernier garde-fou qui empêche un import à zéro course
de passer pour un succès, `import_service` traitant « aucun résultat » comme un
court-circuit légitime.

Aucune migration, aucun changement de contrat API ou CLI, aucun toucher au front.

## Technical Context

**Language/Version**: Python 3.13

**Primary Dependencies**: httpx (client HTTP), aucune nouvelle dépendance —
la source rend du JSON, ni BeautifulSoup ni Playwright ne sont nécessaires

**Storage**: PostgreSQL (prod) / SQLite (dev) via le modèle existant — aucune
migration Alembic

**Testing**: pytest, `httpx.Client` monkeypatché, fixtures JSON sous
`backend/tests/fixtures/` ; réseau réel isolé derrière le marker `integration`

**Target Platform**: backend FastAPI (Render), CLI de batch

**Project Type**: web application — cette feature ne touche que `backend/`

**Performance Goals**: import de l'épreuve du Sheet (955 participations,
6 courses) en une opération ; ≈ 100 requêtes HTTP séquentielles, soit ~30 s.
Pas d'objectif de latence : le chemin est un import de fond (SSE ou CLI), déjà
protégé par le cache TTL.

**Constraints**: `size` ≤ 10 imposé par la source (non contournable, aucun export
CSV) ; API publique sans authentification ; un import refusé doit être rejouable
plutôt que d'enregistrer un classement tronqué

**Scale/Scope**: 1 lien dans le Sheet aujourd'hui ; panel de validation de
7 événements / 32 courses / 10 360 participations. 1 nouveau module scraper,
1 entrée de registre, 1 module de tests, ~10 fixtures.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.0.0).
Statuts autorisés : ✅ conforme / ⚠️ justifié (ligne à créer dans Complexity
Tracking) / N/A (le principe ne s'applique pas à cette feature).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants, docstrings techniques et noms de tests en anglais ; messages de `ValueError` destinés à l'opérateur et libellés de splits (visibles dans le front) en français. Tranché en Clarifications de la spec. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | Le module vit dans `app/scrapers/`, ne connaît ni `Session` ni repository, et rend des `ScrapedResult`. L'appartenance club n'est **pas** réimplémentée : le scraper renseigne `club`, et `core/club.py` reste seul juge (contrairement à t2area, qui doit filtrer, ce scraper n'a aucune raison de connaître le TCN). |
| III | TDD sans réseau (non-négociable) | ✅ | Test rouge avant chaque comportement ; `httpx.Client` monkeypatché ; fixtures JSON extraites du panel ; un seul test `integration` pour le schéma réel. Cf. D13. |
| IV | Contrats API et CLI stables | ✅ | Aucun changement de contrat : `/scrape/detect` rend un provider de plus par dérivation de `PROVIDERS`, les bilans CLI gagnent une cause d'erreur de plus dans un champ existant. Aucun champ retiré, aucune sémantique inversée. |
| V | Neutralité par défaut des paramètres transverses | N/A | Cette feature n'introduit ni ne modifie aucun paramètre transverse d'API de lecture. |
| VI | Simplicité / YAGNI | ✅ | Aucune abstraction nouvelle : le module suit le patron d'`oktime.py`. Les helpers partagés (`normalize_time`, `split_athlete_name`, `derive_status_from_label`, `qualify_event_name`, `classify_event_type`) sont réutilisés, pas réécrits. Aucune factorisation opportuniste des scrapers existants (cf. la note d'en-tête de `registry.py`). |

Aucun principe en ⚠️ : la section « Complexity Tracking » reste vide.

### Re-check post-design — 30/07/2026

Les cinq arbitrages du 30/07 repassent la grille. Aucun ne dégrade un statut ;
trois demandaient une vérification dans le code, faite avant de trancher.

| # | Principe | Statut | Ce que la révision change |
|---|----------|--------|----------------------------|
| I | Langue | ✅ | Deux natures de texte cohabitent et restent séparées : les journaux d'écart de course (FR-008a, FR-008b) sont des `logger.*` **techniques en anglais** (destinés à Sentry, jamais affichés) ; le message de refus à zéro course (FR-008c) est en **français**, parce qu'il traverse `ScraperError` et est réaffiché verbatim par le front — cas mixte `DomainError` du principe I. |
| II | Architecture en couches | ✅ | Point vérifié : poser `status` explicitement (FR-014a) n'introduit **aucun** couplage `scrapers → services`. `STATUS_FINISHER` / `STATUS_DNF` vivent dans `scrapers/base.py`, la couche la plus basse, importée par les scrapers **et** par `services/mapping` ; le contrat de `ScrapedResult` prévoit déjà qu'un scraper qui sait se prononce (précédent prolivesport). Le club reste jugé par `core/club.py` seul. |
| III | TDD sans réseau | ✅ | Trois cas de test s'ajoutent, tous fabriqués à la main faute d'occurrence au panel : course à `classificationsCount: 0`, événement intégralement écarté, participant sans temps ni `validity` mais classé (D13). Toujours aucun accès réseau hors marker `integration`. |
| IV | Contrats API et CLI stables | ✅ | Inchangé, et c'est précisément l'argument de FR-008c : le contrat de sortie de la CLI (`0` succès, `1` échec total) n'est **pas** modifié — on évite au contraire de lui faire dire « succès » sur un import à zéro participation. Aucun champ de bilan ajouté (l'escalade est explicitement renvoyée à un ticket suiveur). |
| V | Neutralité par défaut | N/A | Toujours aucun paramètre transverse d'API de lecture touché. |
| VI | Simplicité / YAGNI | ✅ | Deux tentations écartées nommément : ajouter un canal d'avertissement par épreuve traversant `ScrapedResult` → `import_service` → `batch` (pour remonter une course écartée au bilan), et ajouter `city` / `country` à `ScrapedResult` pour brancher le géocodage. Les deux toucheraient un contrat partagé par douze fournisseurs pour un cas sans occurrence mesurée ; les deux sont documentés en alternatives rejetées (D4, D15) avec la condition qui les rouvrirait. |

Toujours aucune violation : « Complexity Tracking » reste vide.

## Project Structure

### Documentation (this feature)

```text
specs/004-sporthive-scraper/
├── plan.md              # Ce fichier
├── spec.md              # Cadrage (/speckit-specify)
├── research.md          # Phase 0 — 13 décisions de design
├── data-model.md        # Phase 1 — correspondance source → ScrapedResult
├── quickstart.md        # Phase 1 — comment vérifier
├── checklists/
│   └── requirements.md  # Qualité de la spec
├── contracts/
│   └── provider-contract.md   # Phase 1 — contrat ScraperProtocol + invariants
└── tasks.md             # Phase 2 (/speckit-tasks — pas créé ici)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── scrapers/
│       ├── sporthive.py          # NOUVEAU — le scraper
│       └── registry.py           # MODIFIÉ — SporthiveProvider + entrée PROVIDERS
└── tests/
    ├── test_sporthive.py         # NOUVEAU — tests unitaires (sans réseau)
    ├── test_registry.py          # MODIFIÉ — détection + non-régression SSRF
    ├── test_integration_scrapers.py  # MODIFIÉ — 1 test réseau réel
    └── fixtures/
        ├── sporthive_event.json            # NOUVEAU — métadonnées d'événement
        ├── sporthive_races.json            # NOUVEAU — 6 courses
        ├── sporthive_participants_p0.json  # NOUVEAU — triathlon, 5 legs
        ├── sporthive_participants_p1.json  # NOUVEAU — dernière page (last)
        ├── sporthive_kids.json             # NOUVEAU — course à 4 legs
        ├── sporthive_monosport.json        # NOUVEAU — 1 leg, sportName null
        ├── sporthive_statuses.json         # NOUVEAU — DNF / DNS / DQ + leg fantôme
        ├── sporthive_relay.json            # NOUVEAU — lignes d'équipe
        ├── sporthive_races_empty.json      # NOUVEAU — course à classificationsCount 0
        └── sporthive_no_time_ranked.json   # NOUVEAU — ni chip, ni gun, ni validity, mais classé

docs/superpowers/specs/
└── 2026-07-29-sporthive-sondage.md   # DÉJÀ ÉCRIT — vérité de terrain

AGENTS.md                              # MODIFIÉ — §Fournisseurs supportés
```

**Structure Decision**: application web à deux briques, mais cette feature est
**exclusivement backend**. Le front n'est pas touché : il ne tient aucune liste
de fournisseurs (il lit `is_supported` de l'API), et les libellés de splits
passent par le chemin générique existant de `lib/utils/splits.ts`. Le module
scraper se place à côté de ses pairs dans `app/scrapers/`, sans sous-package :
c'est un fichier unique, comme `oktime.py` (682 lignes) et `t2area.py`.

## Découpage d'implémentation

Séquence proposée à `/speckit-tasks`, chaque étape en TDD (test rouge d'abord).
Les étapes 3 à 6 sont indépendantes entre elles et parallélisables `[P]` une fois
l'étape 2 posée.

| # | Étape | Couvre |
| --- | --- | --- |
| 1 | Lecture d'URL : `_parse_url`, formes acceptées et refusées | FR-001..FR-004, D1, D3 |
| 2 | Client API : `_fetch_event`, `_fetch_races`, `_fetch_participants` + pagination, plafond, traduction des 404 | FR-007, FR-009, D4 |
| 3 | Garde de complétude sur `classificationsCount` : `_IncompleteRanking` (portée course) + journal, courses à zéro classé ignorées sans requête | FR-008, FR-008a, FR-008b, D4, D14 |
| 4 | Mapping des scalaires : temps, rangs, genre, statut (dont le repli sur le rang quand ni temps ni `validity`), club, identité | FR-010..FR-015, **FR-014a**, FR-019, D5, D6, D11, D12 |
| 5 | Segments depuis `legs`, leg fantôme écarté | FR-016, FR-017, D7, D8 |
| 6 | Métadonnées d'épreuve : nom qualifié, date, classification, distance, `is_relay`, lieu / pays en `raw_data` | FR-006, FR-018, FR-020..FR-022, **FR-022a**, D9, D10, D15 |
| 7 | Assemblage `scrape_event_all` : boucle sur les courses, écart des fautives, refus si zéro course rendue, puis enregistrement au registre | FR-005, **FR-008c**, FR-023, D14 |
| 8 | Test `integration` sur l'événement du Sheet | SC-002, D13 |
| 9 | Documentation : `AGENTS.md` §Fournisseurs supportés | — |

Les arbitrages du 30/07 n'ajoutent aucune étape : ils épaississent 3, 4, 6 et 7.
L'étape 7 cesse d'être un simple assemblage — c'est elle qui porte la boucle et
les deux portées d'échec, donc elle **dépend** de 3 et n'est plus parallélisable
avec elle. Les étapes 4, 5 et 6 restent indépendantes entre elles (`[P]`).

FR-024 (échecs au bilan CLI) et FR-025 (cache TTL) ne demandent **aucun code** :
ils sont satisfaits par l'infrastructure existante dès lors que le scraper lève
une `ValueError` porteuse d'un message utile. Une tâche de vérification les
couvre, pas une tâche d'implémentation.

## Risques

| Risque | Probabilité | Mitigation |
| --- | --- | --- |
| MYLAPS redéplace son API (c'est déjà arrivé, cf. le host mort de l'issue) | moyenne | Le test `integration` casse en premier ; `quickstart.md` documente que `GET sporthive.com/api/clientSettings` est la source de vérité de l'adresse |
| Le plafond de 10 baisse encore, ou un throttling apparaît | faible | La pagination est déjà séquentielle et lente ; un 429 remonterait comme erreur HTTP, l'import se rejoue |
| Un événement très gros rend l'import long (2 685 classés = 269 requêtes) | avérée au panel | Accepté : import de fond, protégé par le cache TTL. Le plafond `_MAX_PAGES` borne le pire cas |
| Sous-classements dupliquant des participations | avérée au panel | Accepté au cadrage, documenté en Assumptions de la spec |
| Une course écartée passe inaperçue : le bilan CLI comptant des épreuves, l'épreuve ressort en succès à 5 courses sur 6 | faible (0 cas au panel) | Conséquence assumée de l'écart par course (FR-008a). Mitigation : le `logger.warning` porte intitulé, `activeRaceId` et les deux décomptes, donc il est exploitable seul. Escalade prévue si le cas se produit : remonter l'avertissement jusqu'au bilan, ce qui suppose un canal par épreuve dans `import_service` et `batch` (écarté aujourd'hui par principe VI) |
| Une course annoncée à zéro classé alors que son classement existe est ignorée sans requête | faible (0 cas au panel) | `classificationsCount` est la seule vérité annoncée par la source ; le `logger.info` d'omission rend le cas diagnosticable, et un re-scrape le rattrape dès que le compteur passe à non nul |

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucune violation : la grille Constitution Check ne porte ni ⚠️ ni dérogation.

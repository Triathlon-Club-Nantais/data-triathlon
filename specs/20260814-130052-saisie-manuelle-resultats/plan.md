# Implementation Plan: Refonte du formulaire de saisie manuelle des résultats

**Branch**: `20260814-130052-saisie-manuelle-resultats` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/20260814-130052-saisie-manuelle-resultats/spec.md`

**Issue**: Closes #270

## Summary

Le formulaire de saisie manuelle demande aujourd'hui à l'athlète ce qu'il ne sait
pas (catégorie, libellé exact du club) et ne demande pas ce qui fait la valeur du
résultat (place, équipe, preuve). Surtout, ce qu'il produit entre en base au même
niveau de confiance qu'un résultat chronométré.

La feature restructure le formulaire — quatre champs obligatoires avec contrôles
bloquants, trois champs retirés, taxonomie FFTri complétée, format en deux temps,
statut sportif déclarable — et introduit un **état de validation** porté
indépendamment du statut sportif. Un résultat déclaré n'est visible que sur la
fiche de son athlète et ne compte dans **aucun** agrégat public tant qu'un
bénévole ne l'a pas vérifié.

**Approche technique**, issue de [research.md](./research.md) :

1. **Une migration Alembic, quatre colonnes, aucun backfill** —
   `is_pending_validation`, `team_name`, `evidence_url` sur `participations`,
   `format_label` sur `courses`.
2. **Un point unique d'exclusion** — `app/core/validation.py`, sur le patron
   littéral de `core/club.tcn_clause` et `core/discipline.federal_clause`,
   appliqué à cinq fonctions de `participation_repository.py` et délibérément
   absent de six autres, la répartition étant verrouillée par un test.
3. **13 slugs de discipline** à déclarer aux quatre endroits qui les connaissent,
   dont trois bases multi-mots qui sont le piège central du lot.
4. **Le lien saisi n'est pas une source** — il va dans `evidence_url`, jamais en
   `CourseSource`, sous peine d'entrer dans le circuit de re-scrape.

## Technical Context

**Language/Version**: Python 3.13 (backend) · TypeScript strict (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, Alembic ·
Next.js 16 (App Router), Tailwind, shadcn/ui, react-hook-form + zod

**Storage**: PostgreSQL (Supabase) en production, SQLite en développement et en
test. Migrations Alembic — jamais de `create_all` hors fixtures.

**Testing**: pytest (marker `integration` pour le réseau réel, jamais en CI) ·
vitest + RTL

**Target Platform**: backend sur Render, frontend sur Vercel

**Project Type**: application web à deux applications (`backend/` + `frontend/`)

**Performance Goals**: aucun objectif nouveau. La feature ajoute un prédicat
booléen à cinq requêtes existantes, sur des sélections déjà restreintes par
`course_id`, saison ou portée club.

**Constraints**: temps toujours en chaînes normalisées `HH:MM:SS` · cache TTL
inchangé (`is_fresh`) · l'API `/api/v1` publiée ne perd aucun champ

**Scale/Scope**: 20 318 participations et 98 épreuves en base de dev (relevé du
2026-08-14) · 4 colonnes · 5 sites d'exclusion · 13 slugs · 1 composant front
réécrit

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Passage explicite des 6 principes de `.specify/memory/constitution.md` (v1.1.1).

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants et tests en anglais (`is_pending_validation`, `team_name`, `evidence_url`, `format_label`, `validated_clause`) ; libellés d'écran, messages de validation et docs produit en français. Aucun identifiant d'une ou deux lettres introduit. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | La clause d'exclusion vit dans `core/` (aucun état, aucun accès base — comme `club.py` et `discipline.py`) et n'est **appliquée** que dans `repositories/`. La route force `is_pending_validation`, le service le propage, le repository filtre. Aucune nouvelle `Session` hors repository. |
| III | TDD sans réseau (non-négociable) | ✅ | Chaque lot ouvre par ses tests rouges. Aucun test n'appelle le réseau : la saisie manuelle ne scrape rien, et les tests de non-régression d'import réutilisent les fixtures existantes. |
| IV | Contrats API et CLI stables | ✅ | Additif seulement — voir research.md D9 et [contracts/participations-api.md](./contracts/participations-api.md). Aucun champ retiré (`gender`, `club`, `category` restent au schéma, seul le formulaire cesse de les proposer), aucun code de retour modifié, aucune CLI touchée. |
| V | Neutralité par défaut des paramètres transverses | ⚠️ | L'exclusion des résultats en attente est **imposée** par l'API sans paramètre pour la lever. Justifiée ci-dessous. |
| VI | Simplicité / YAGNI | ✅ | Un booléen plutôt qu'une machine à états ou une table dédiée ; réutilisation de `rank_overall`, `is_relay`, `distance_km` et `derive_status` existants ; aucun `include_pending` spéculatif ; aucune abstraction de formulaire générique. |

## Project Structure

### Documentation (this feature)

```text
specs/20260814-130052-saisie-manuelle-resultats/
├── plan.md                          # Ce fichier
├── spec.md                          # 25 exigences, 4 user stories
├── research.md                      # Phase 0 — 9 décisions
├── data-model.md                    # Phase 1 — 4 colonnes, 13 slugs
├── quickstart.md                    # Phase 1 — guide de vérification
├── contracts/
│   └── participations-api.md        # Phase 1 — contrat d'entrée/sortie
├── checklists/
│   └── requirements.md              # 16/16
└── tasks.md                         # Phase 2 — /speckit-tasks, pas créé ici
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── <rev>_manual_result_validation.py     # NOUVEAU — 4 colonnes
├── app/
│   ├── core/
│   │   └── validation.py                     # NOUVEAU — is_pending + validated_clause
│   ├── models/
│   │   ├── participation.py                  # +3 colonnes
│   │   └── course.py                         # +1 colonne
│   ├── schemas/
│   │   └── participation.py                  # ParticipationCreate +4, ParticipationOut +3
│   ├── api/v1/
│   │   └── participations.py                 # _to_scraped + forçage de l'état
│   ├── services/
│   │   └── mapping.py                        # participation_fields, _SPLIT_KEYS_BY_SPORT, _MULTI_WORD_BASES +3
│   ├── scrapers/
│   │   ├── base.py                           # ScrapedResult porte l'état + team_name/evidence_url
│   │   ├── classify.py                       # CANONICAL_TYPES +13 (rien d'autre — cf. research.md D3)
│   │   └── AGENTS.md                         # la liste des types d'épreuve en pied de page suit
│   └── repositories/
│       └── participation_repository.py       # 5 sites filtrés, 6 non filtrés
└── tests/
    ├── test_api/test_participations_api.py
    ├── test_repositories/test_pending_exclusion.py   # NOUVEAU — le verrou des 11 fonctions
    ├── test_services/test_mapping.py
    └── test_migrations.py

frontend/
├── lib/
│   ├── constants.ts                          # EVENT_TYPE_LABELS +13
│   └── types.ts                              # Participation +3 champs
└── components/
    ├── scrape/
    │   ├── ManualResultForm.tsx              # réécrit
    │   ├── ManualResultForm.test.tsx         # NOUVEAU
    │   └── TcnScrapeForm.tsx                 # cesse de passer defaultUrl en source_url
    └── results/
        └── ResultCard.tsx                    # mention « en attente de validation »
```

**Structure Decision**: application web à deux applications, structure existante
inchangée. Un seul module backend est créé (`core/validation.py`) ; tout le reste
modifie des fichiers en place. Aucun nouveau dossier, aucune nouvelle couche.

## Ordre d'exécution recommandé

Quatre lots, alignés sur les priorités de la spec. Chacun est livrable et
vérifiable seul.

| Lot | Contenu | User Story | Dépend de |
| --- | --- | --- | --- |
| **1 — Socle de données** | migration, 4 colonnes, `core/validation.py`, les 5 sites d'exclusion + le test de répartition, schémas Pydantic | US2 (backend) | — |
| **2 — Formulaire, socle** | champs obligatoires, retraits, libellé, contrôles bloquants | US1 | 1 (schémas) |
| **3 — Taxonomie** | 13 slugs aux 4 endroits, sélection en deux temps, distance totale | US3 | 2 |
| **4 — Qualification** | place, collectif + équipe, statut sportif, lien, encart temps, mention front | US4 + US2 (front) | 1, 2 |

**Le lot 1 passe avant tout**, et ce n'est pas un détail d'ordonnancement : c'est
lui qui porte l'invariant de FR-021. Les livrer dans l'ordre inverse ferait entrer
des résultats déclarés dans les podiums pendant la durée du chantier.

## Complexity Tracking

> Rempli parce que le Constitution Check porte une violation à justifier.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principe V** — l'exclusion des résultats en attente est imposée par l'API de lecture, sans paramètre transverse permettant de la lever | FR-021 est un invariant d'intégrité, pas une préférence d'affichage : un résultat non vérifié ne doit **pas pouvoir** compter dans un podium ou une statistique publique. Le rendre optionnel rendrait l'invariant contournable par n'importe quel appelant, y compris le front du site, et un oubli d'appelant réinjecterait silencieusement des données non vérifiées — exactement ce que la feature existe pour empêcher. | Un paramètre `include_pending` à **défaut neutre** (donc incluant les pendantes) aurait respecté la lettre du Principe V tout en inversant son intention : le défaut neutre exigé par le principe est précisément celui qui casse FR-021. Un paramètre à défaut `false` aurait, lui, été le « défaut intelligent » que le même principe proscrit. La sortie est ailleurs : la file de #271 lira les pendantes par une fonction de repository dédiée derrière une route `/admin/` gardée, patron déjà en place dans `admin_feedback.py`. Le Principe V garde ainsi sa portée — les trois paramètres qu'il nomme (`scope`, `federal_only`, `seasons`) restent neutres et ne sont pas touchés. |

## Post-Design Constitution Re-check

Repassage après production de `data-model.md`, `contracts/` et `quickstart.md` :

- **I** ✅ — les quatre colonnes, le module `core/validation.py` et les 13 slugs
  sont en anglais ; les libellés UI (« Nom de l'épreuve », « en attente de
  validation », « Raid Multisport ») et les messages d'erreur du formulaire sont
  en français, comme les `DomainError` sérialisés vers le front.
- **II** ✅ — le design n'a introduit aucun accès `Session` hors repository, et
  `core/validation.py` reste sans état ni import de modèle métier.
- **III** ✅ — `quickstart.md` §1 nomme les commandes de vérification et §8 la
  non-régression d'import.
- **IV** ✅ — le contrat écrit confirme l'additivité ; le seul changement de
  contenu (cinq chemins de lecture) porte sur des lignes qui n'existaient pas
  avant la feature.
- **V** ⚠️ — inchangé, justifié ci-dessus.
- **VI** ✅ — le design a **retiré** du périmètre plutôt qu'ajouté : pas de
  colonne d'état à trois valeurs, pas de table de validation, pas de champ
  d'entrée `is_pending_validation`, `cross-triathlon` sans gabarit de splits
  puisque le défaut est déjà juste, et `core/discipline.py` non touché puisque sa
  liste est une liste d'exclusion.

**Gate franchi** : la seule violation est justifiée avec son alternative rejetée.
Passage à `/speckit-tasks` autorisé.

## Questions tranchées

**« Run & Bike » = le `bike-run` existant — confirmé le 2026-08-14.** Une seule
discipline, donc aucun slug ni libellé supplémentaire : le lot 3 reste à 13 slugs.
`bike-run` garde son libellé « Bike & Run », la forme officielle de la fédération.

**Aucune question ouverte ne subsiste.** Les trois arbitrages de la feature —
exclusion totale des agrégats, statut sportif déclarable, assimilation de
« Run & Bike » — sont tous rendus.

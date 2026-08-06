# Implementation Plan: Lancer les batches de production depuis l'interface d'administration

**Branch**: `20260806-143754-ops-batch-runs` | **Date**: 2026-08-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/20260806-143754-ops-batch-runs/spec.md` · Issue [#47](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/47)

## Summary

Un administrateur lance les batches de résultats depuis `/admin` : soit une
reprise filtrée de la base, soit l'import d'une liste d'épreuves tirée d'un
fichier `.csv`/`.xlsx` dont il désigne la colonne de liens. **L'interface
déclenche, elle n'exécute pas** : le travail part sur un runner GitHub Actions
qui lance la CLI existante, ce qui laisse le service web gratuit de Render
entièrement au site public.

Les deux modes convergent immédiatement : le mode fichier ne fait que **produire
une liste d'URL**, et les deux finissent en `rescrape-db`. Un seul chemin
d'exécution, un seul format de bilan, un seul mécanisme d'alerte.

Rien n'est ajouté au schéma de la base : ni table de lancements, ni migration.
L'état d'un lancement est celui que la plateforme d'exécution tient déjà.

## Technical Context

**Language/Version** : Python 3.13 (backend), TypeScript 5 / Node 26 (frontend)

**Primary Dependencies** : FastAPI, Pydantic v2, SQLAlchemy 2.0, Typer, httpx
(via `core/http`) ; **ajout : `openpyxl`** (lecture `.xlsx`). Côté front, Next.js
16 App Router, TanStack Query, shadcn/ui — aucune dépendance nouvelle.

**Storage** : aucune nouvelle table. Les lancements et leurs bilans vivent chez
la plateforme d'exécution ; l'API les relaie.

**Testing** : pytest sans réseau (`httpx.MockTransport` pour l'API GitHub,
classeurs `.xlsx` fabriqués en mémoire par `openpyxl` dans les tests) ; Vitest +
Testing Library côté front.

**Target Platform** : API sur Render (offre gratuite), interface sur Vercel,
exécution des batches sur runner GitHub Actions `ubuntu-latest`.

**Project Type** : application web (backend + frontend), plus un workflow
d'intégration continue.

**Performance Goals** : le lancement (dispatch) répond en moins de 2 s ; la
consultation d'un bilan en moins de 3 s, téléchargement de l'artefact compris.
La durée du batch lui-même est celle du scraping, hors périmètre.

**Constraints** : fichier ≤ 2 Mo, ≤ 500 URL par lot ; aucun fichier conservé côté
serveur au-delà de la requête ; un seul batch à la fois ; aucune entrée
utilisateur interpolée dans un script shell.

**Scale/Scope** : une poignée de lancements par mois, ~50 à 500 épreuves par lot,
2 à 3 administrateurs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principe | Statut | Justification (si ⚠️ ou N/A) |
|---|----------|--------|-------------------------------|
| I | Langue métier français / technique English | ✅ | Identifiants, tests et docstrings techniques en anglais (`read_table`, `links_in_column`, `batch_runs`) ; libellés de pouvoirs, messages d'erreur rendus et écrans en français. Les ajouts suivent la règle sans exception de vocabulaire métier. |
| II | Architecture en couches (api → services → repositories → DB) | ✅ | `api/v1/admin_batches.py` valide et délègue ; `services/batch_runs.py` porte le dialogue avec la plateforme ; `services/sheet_source.py` reste sans base ni état. Aucun accès `Session` hors repositories — cette feature n'en ouvre aucun. |
| III | TDD sans réseau (non-négociable) | ✅ | L'API GitHub est jointe par `core/http.client()`, donc interceptable par `MockTransport` comme les scrapers. Aucun test ne sort. |
| IV | Contrats API et CLI stables | ✅ | Ajouts seuls sous `/api/v1` ; aucune route existante modifiée. La CLI n'est pas touchée : le workflow **dépend** de ses codes de sortie et de sa séparation stdout/stderr, il ne les change pas. |
| V | Neutralité par défaut des paramètres transverses | N/A | Aucun endpoint de lecture transverse (`scope`, `federal_only`, `seasons`) n'est introduit ni modifié. |
| VI | Simplicité / YAGNI | ✅ | Pas de table de lancements, pas de file d'attente, pas de stockage de fichier, pas de second extracteur de colonne. Les trois sont des replis documentés dans `research.md`, pas des travaux à faire d'avance. |

Aucun principe en ⚠️ : la section « Complexity Tracking » est vide et reste
supprimée.

### Re-check après Phase 1

Inchangé. Les contrats de la Phase 1 n'ajoutent ni table, ni couche, ni
dépendance au-delà d'`openpyxl` — dont la justification (une seule brique
manquante, le CSV restant en stdlib) est écrite en D8.

## Project Structure

### Documentation (this feature)

```text
specs/20260806-143754-ops-batch-runs/
├── plan.md              # Ce fichier
├── spec.md              # Exigences (/speckit-specify)
├── research.md          # Phase 0 — 14 décisions
├── data-model.md        # Phase 1 — entités, toutes hors base
├── quickstart.md        # Phase 1 — validation de bout en bout
├── contracts/
│   ├── admin-batches.md # Contrat HTTP des cinq routes
│   └── workflow.md      # Contrat d'entrée et de sortie du workflow
├── checklists/
│   └── requirements.md  # Qualité de la spec (16/16)
└── tasks.md             # Phase 2 (/speckit-tasks — pas créé ici)
```

### Source Code (repository root)

```text
.github/workflows/
└── batch.yml                          # CRÉÉ — workflow_dispatch + schedule

backend/
├── app/
│   ├── core/
│   │   ├── config.py                  # MODIFIÉ — 3 réglages GitHub
│   │   └── permissions.py             # MODIFIÉ — batch:run, batch:read
│   ├── schemas/
│   │   └── batch_run.py               # CRÉÉ — DTO d'entrée et de sortie
│   ├── services/
│   │   ├── sheet_source.py            # MODIFIÉ — read_table, links_in_column
│   │   └── batch_runs.py              # CRÉÉ — dispatch, liste, bilan
│   └── api/v1/
│       ├── admin_batches.py           # CRÉÉ — 5 routes gardées
│       └── router.py                  # MODIFIÉ — montage
├── pyproject.toml                     # MODIFIÉ — openpyxl
└── tests/
    ├── test_services/
    │   ├── test_sheet_source_upload.py   # CRÉÉ
    │   └── test_batch_runs.py            # CRÉÉ
    └── test_api/
        └── test_admin_batches.py         # CRÉÉ

frontend/
├── app/admin/batches/page.tsx         # CRÉÉ — écran de lancement
├── components/admin/
│   ├── BatchLauncher.tsx              # CRÉÉ — mode reprise filtrée
│   ├── SheetUpload.tsx                # CRÉÉ — téléversement + choix de colonne
│   ├── BatchRunList.tsx               # CRÉÉ — état et bilans
│   └── *.test.tsx                     # CRÉÉ
├── lib/api/client.ts                  # MODIFIÉ — envoi multipart + 3 méthodes
├── lib/queries/batches.ts             # CRÉÉ
└── lib/types.ts                       # MODIFIÉ

docs/
└── ci-cd.md                           # MODIFIÉ — environment, secrets, jeton, repli
```

**Structure Decision** : structure existante du dépôt (backend en couches,
frontend App Router), plus un troisième lieu qui n'existait pas encore comme
cible de livraison — `.github/workflows/`. C'est le point notable de cette
feature : une partie du produit est un workflow d'intégration continue, et il se
relit comme du code de production (D3 sur l'injection, D5 sur la concurrence).

## Découpage par histoire utilisateur

L'ordre suit les priorités de la spec, et chaque étage se livre seul.

### US1 — Reprise filtrée (P1) — le socle

Workflow `batch.yml` (mode filtre uniquement), les deux pouvoirs et leurs gardes,
`services/batch_runs.py` (dispatch, liste des exécutions, bilan), trois des cinq
routes (`POST /admin/batches`, `GET /admin/batches`,
`GET /admin/batches/{id}/report`), l'écran de lancement et la liste des
exécutions.

Livrable seul, et c'est ce qui supprime la dépendance au poste de développement.

### US2 — Import d'un fichier (P2)

`read_table` / `links_in_column`, la route de listage des colonnes, l'entrée
`urls` du workflow, l'écran de téléversement en deux temps.

Dépend d'US1 pour tout l'aval — dispatch, suivi, bilan.

### US3 — Reprise périodique (P3)

Ajout du `schedule` au workflow et la documentation de la cadence. Quelques
lignes, une fois qu'US1 a prouvé qu'une exécution aboutit.

## Livraison : deux PR, et ce n'est pas un choix de confort

**Un `workflow_dispatch` n'existe que si le fichier de workflow est sur la branche
par défaut** — la documentation GitHub est explicite : « This event will only
trigger a workflow run if the workflow file exists on the default branch. » Tant
que `batch.yml` vit sur une branche de feature, il est **indéclenchable**, par
l'interface comme par l'API.

D'où deux PR, dans cet ordre :

1. **PR 1 — le workflow seul** : dépendances et réglages (Phase 1), `batch.yml`
   (Phase 2), plus l'environment `batch-production` et son secret. Une fois
   mergée, le workflow est déclenchable depuis l'onglet Actions.
2. **PR 2 — le reste** : client de la plateforme, routes, écran, US2, US3.

Le bénéfice dépasse la contrainte : c'est **le seul ordre où l'on apprend que la
connexion à la base échoue (D12) avant d'avoir construit dessus**. Dans une
livraison monolithique, la découverte arriverait à la toute fin, après l'API et
l'écran.

Corollaire : le repli exigé par FR-020 — lancer sans l'interface — existe donc
**dès la PR 1**, et il est validé avant que l'interface n'existe.

## Risques et ce qui les couvre

| Risque | Couverture |
| --- | --- |
| Injection de commande par une entrée du workflow | D3 — `env:` obligatoire, aucune interpolation dans `run:`. Critère de relecture. |
| Connexion à Supabase impossible depuis le runner (IPv6) | D12 — viser le pooler, vérifié avant la première exécution réelle. |
| Chronométreur bloquant une IP de centre de données | Premier lancement en simulation, puis lot réel borné (quickstart §5). |
| Jeton GitHub expiré | Message d'erreur qui le nomme, procédure de régénération dans `docs/ci-cd.md`. |
| Colonne XLSX sans lien lisible (hyperlien, formule) | D8 — le compte de liens par colonne le rend visible **avant** de lancer. |
| Workflow planifié désactivé après 60 jours d'inactivité | D13 — SC-007 (quatre échéances consécutives) est le test qui le révélerait. |

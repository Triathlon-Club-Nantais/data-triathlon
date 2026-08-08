---

description: "Tâches d'implémentation — lancer les batches depuis l'interface d'administration"
---

# Tasks: Lancer les batches de production depuis l'interface d'administration

**Input**: `specs/20260806-143754-ops-batch-runs/` — plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Principe III de la constitution — TDD sans réseau, **non-négociable**.
Chaque story porte ses tâches de test **avant** l'implémentation qu'elles
décrivent. Aucun test ne sort sur le réseau : l'API de la plateforme d'exécution
est jointe par `core/http.client()`, donc interceptable par `httpx.MockTransport`,
et les classeurs `.xlsx` sont fabriqués en mémoire dans les tests.

**Organization**: par user story, chacune livrable et testable seule.

**Livraison en deux PR** — contrainte de plateforme, pas de confort : un
`workflow_dispatch` n'est déclenchable que si le fichier de workflow est sur la
branche par défaut. La **PR 1** livre le workflow seul et le rend exécutable ; la
**PR 2** livre tout le reste. C'est aussi le seul ordre où le piège de connexion
(D12) se découvre avant qu'on ait construit dessus.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : parallélisable (fichiers distincts, aucune dépendance en cours)
- **[Story]** : US1, US2, US3 — absent en Setup, Foundational et Polish

---

# PR 1 — Le workflow seul

## Phase 1: Setup

- [X] T001 [P] Ajouter `openpyxl` aux dépendances de `backend/pyproject.toml`, puis régénérer `backend/uv.lock` (`uv lock`) — la CI échoue sur `uv sync --locked` si le lock diverge
- [X] T002 [P] Ajouter trois réglages à `backend/app/core/config.py` — `github_batch_token: str = ""`, `github_repository: str = "Triathlon-Club-Nantais/data-triathlon"`, `github_workflow_file: str = "batch.yml"` — et les documenter dans `backend/.env.example` ; un jeton vide est un état légitime (D4), pas une erreur de démarrage

## Phase 2: Le workflow d'exécution

- [X] T003 Créer `.github/workflows/batch.yml` — `workflow_dispatch` avec les huit entrées de `contracts/workflow.md` (dont `target`, qui choisit la base), `concurrency: { group: batch-<cible>, cancel-in-progress: false }` — un verrou par base, pas un verrou global, `run-name` portant `correlation_id`, checkout + `astral-sh/setup-uv` + `uv sync --locked` alignés sur `ci.yml`
- [X] T004 Poser `timeout-minutes: 120` sur le job de `.github/workflows/batch.yml` — sans cette borne, une exécution coincée gèle tout nouveau lancement pendant six heures (défaut de la plateforme), ce que l'edge case « traitement qui n'aboutit jamais » proscrit
- [X] T005 Écrire l'étape d'exécution de `.github/workflows/batch.yml` — **aucune interpolation `${{ inputs.… }}` dans un `run:`** (D3) : chaque valeur passe par `env:` et n'est lue que citée. Redirection : stdout (`--json`) vers le fichier d'artefact, stderr vers le journal
- [X] T006 Ajouter à `.github/workflows/batch.yml` le rendu du rapport texte dans `$GITHUB_STEP_SUMMARY` et le dépôt de l'artefact `bilan-<correlation_id>.json` via `actions/upload-artifact`
- [X] T007 Écrire `backend/tests/test_workflows.py` — méta-test des invariants du workflow : aucune entrée interpolée dans un `run:` (D3), verrou de concurrence, borne de durée. Remplace le `grep` initialement prévu, qui marquait en faute le bloc `env:`, c'est-à-dire la forme correcte
- [ ] T008 Créer l'environment GitHub `batch-production` et son secret `DATABASE_URL` **visant le pooler Supabase** (D12) — *action manuelle, dans le dashboard GitHub ; la documentation correspondante est écrite dans `docs/ci-cd.md` (hôte, motif, symptôme d'erreur)*
- [X] T009 Ouvrir et faire fusionner la **PR 1** avec `Refs #47` — le workflow doit être sur `main` pour devenir déclenchable
- [X] T010 Exécuter `specs/20260806-143754-ops-batch-runs/quickstart.md` §7 — `mode: rescrape`, `limit: 1`, `dry_run: true` depuis l'onglet Actions. **Aucune tâche de la PR 2 ne commence avant que celle-ci soit verte** : c'est elle qui révèle D12, et le repli de FR-020 est acquis dès ici

---

# PR 2 — API, interface, import de fichier

## Phase 3: Foundational — le client de la plateforme

**Purpose**: le dialogue avec la plateforme d'exécution. Ne livre rien
d'utilisable seul, mais les trois stories s'y appuient.

**⚠️ À terminer avant toute story.**

- [X] T011 Écrire `backend/tests/test_services/test_batch_runs.py` — cas du **dispatch** : corps envoyé (`ref: "main"`, `inputs` exactement les huit entrées du contrat, `target` valant le réglage `GITHUB_BATCH_TARGET` de l'instance et jamais une valeur reçue du client), en-têtes (`Authorization: Bearer`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version`), URL construite depuis les réglages, `correlation_id` de huit caractères hexadécimaux ; `MockTransport`, aucun réseau
- [X] T012 Implémenter `dispatch_batch()` dans `backend/app/services/batch_runs.py` — passe par `core/http.client()` (jamais `httpx` nu : un méta-test l'interdit dans `app/`), produit le `correlation_id` par `uuid4().hex[:8]` et le rend
- [X] T013 Compléter `backend/tests/test_services/test_batch_runs.py` — **liste des exécutions** : correspondance statut/conclusion de la plateforme → `state` (`pending`/`running`/`completed`), `outcome` (`success`/`failure`/`cancelled`) et `triggered_by` (`ui`/`schedule`/`manual`) ; tri décroissant, borne `limit` ; plateforme injoignable → erreur dédiée, jamais une liste vide
- [X] T014 Implémenter `list_runs()` dans `backend/app/services/batch_runs.py` — valeurs d'énumération **en anglais** (Principe I) ; la traduction d'affichage appartient au front
- [X] T015 Compléter `backend/tests/test_services/test_batch_runs.py` — **bilan** : l'artefact est un zip, son unique entrée JSON est rendue telle quelle ; artefact absent → erreur « pas de bilan », artefact expiré (410 amont) → erreur distincte
- [X] T016 Implémenter `fetch_report()` dans `backend/app/services/batch_runs.py` — `zipfile.ZipFile(io.BytesIO(...))`, aucune écriture disque
- [X] T017 Compléter `backend/tests/test_services/test_batch_runs.py` — **configuration et jeton** : jeton absent → erreur « lancement non configuré » ; jeton refusé par la plateforme (401) → erreur « jeton expiré ou révoqué ». Les deux messages sont distincts, c'est ce qui rend le diagnostic possible sans accès aux logs
- [X] T018 Implémenter la garde de configuration et la traduction des erreurs amont dans `backend/app/services/batch_runs.py`

## Phase 4: User Story 1 — Reprise filtrée (P1) 🎯 MVP

**Goal**: un administrateur lance une reprise filtrée depuis `/admin` et relit son
bilan sans terminal.

**Independent Test**: quickstart §8 — lancer une reprise `limit: 5`,
`dry_run: true` depuis l'écran, et retrouver son bilan.

### Pouvoirs et gardes

- [X] T019 [US1] Ajouter `P.BATCH_RUN` (`batch:run`, « Lancer un batch ») et `P.BATCH_READ` (`batch:read`, « Consulter les batches ») sous `FEATURE_BATCH = "Batches"` dans `backend/app/core/permissions.py`, et les inscrire dans `ALL` — **le méta-test `tests/test_permissions_catalogue.py` devient rouge ici** : un pouvoir qui ne garde aucune ressource est un défaut, et T023 le referme
- [X] T020 [US1] Écrire `backend/tests/test_api/test_admin_batches.py` — refus : 401 sans session, 403 sans le pouvoir, 409 quand une exécution est `pending`/`running`, 422 sur fournisseur inconnu et bornes dépassées, 503 sans jeton
- [X] T021 [US1] Écrire les cas nominaux dans `backend/tests/test_api/test_admin_batches.py` — 202 avec `correlation_id`, liste rendue par `GET /admin/batches`, bilan rendu **tel quel** par `GET /admin/batches/{id}/report`

### Contrat et routes

- [X] T022 [US1] Créer `backend/app/schemas/batch_run.py` — `RescrapeLaunch` (union discriminée sur `mode`), `BatchRun`, bornes `older_than ∈ 1..3650`, `limit ∈ 1..500`, `provider` validé contre le registre des scrapers
- [X] T023 [US1] Créer `backend/app/api/v1/admin_batches.py` — `POST /admin/batches`, `GET /admin/batches`, `GET /admin/batches/{run_id}/report`, chacune gardée **route par route** par `require_permission(P.BATCH_RUN|P.BATCH_READ)` ; routers fins, toute logique dans `services/batch_runs.py`
- [X] T024 [US1] Monter le router dans `backend/app/api/v1/router.py` — jamais de garde en `dependencies=` de router (le signalement anonyme `POST /admin/pending-providers` vit sous le même préfixe)
- [X] T025 [US1] Vérifier que `tests/test_permissions_catalogue.py` et `tests/test_api/test_admin_batches.py` passent, et que `uv run pytest -m "not integration"` est vert

### Interface

- [X] T026 [P] [US1] Ajouter les types `BatchRun`, `BatchReport`, `RescrapeLaunch` à `frontend/lib/types.ts` — états et issues en anglais, comme le contrat
- [X] T027 [US1] Ajouter à `frontend/lib/api/client.ts` — `launchBatch`, `listBatchRuns`, `getBatchReport`
- [X] T028 [P] [US1] Créer `frontend/lib/queries/batches.ts` — `useBatchRuns` (rafraîchissement pendant qu'une exécution est en cours), `useLaunchBatch`, `useBatchReport` ; clés dans `frontend/lib/queries/keys.ts`
- [X] T029 [US1] Écrire `frontend/components/admin/BatchLauncher.test.tsx` — formulaire de filtres, lancement désactivé pendant une exécution en cours, message d'erreur de l'API affiché **tel qu'il est rendu**, jamais réécrit côté interface
- [X] T030 [US1] Créer `frontend/components/admin/BatchLauncher.tsx` — n'interroge la liste des exécutions **que si la session porte `batch:read`** (connu par `/auth/me`) : un porteur de `batch:run` seul voit le formulaire, jamais un bloc en erreur 403 à la place de l'état courant
- [X] T031 [US1] Écrire `frontend/components/admin/BatchRunList.test.tsx` — états `pending` / `running` / `completed` traduits à l'affichage, issue `failure` renvoyant au bilan sans en affirmer la cause (`data-model.md`), bilan indisponible distingué de bilan vide, exécution `running` depuis plus de deux heures signalée avec le lien pour l'annuler sur sa page
- [X] T032 [US1] Créer `frontend/components/admin/BatchRunList.tsx` — compteurs du bilan avec leurs **unités nommées** : « épreuves » pour `unique_supported`/`processed`/`errors`, « participants » pour `imported`/`updated`/`skipped`
- [X] T033 [US1] Créer `frontend/app/admin/batches/page.tsx` — assemble les deux composants sous `PageShell` / `PageHeader`, comme `app/admin/page.tsx`
- [X] T034 [US1] Vérifier `npm test`, `npm run lint` et `npm run build` verts depuis `frontend/`

**Checkpoint**: US1 livrable — la dépendance au poste de développement est levée.

## Phase 5: User Story 2 — Import d'un fichier (P2)

**Goal**: téléverser un `.csv`/`.xlsx`, désigner la colonne de liens, lancer.

**Independent Test**: quickstart §10 — un fichier réel du club importe ses
épreuves, les liens non supportés listés à part.

### Extraction

- [X] T035 [US2] Écrire `backend/tests/test_services/test_sheet_source_upload.py` — `read_table` sur un `.csv` **et** sur un `.xlsx` fabriqué en mémoire par `openpyxl` ; en-tête vide remplacé par « Colonne N » ; première ligne absente ; classeur illisible → erreur nommée
- [X] T036 [US2] Écrire les cas de `links_in_column` dans le même fichier — comptage des liens par colonne, valeurs non-URL ignorées et comptées, doublons ramenés à une épreuve, partage `supported` / `ignored_by_host`
- [X] T037 [US2] Implémenter `read_table(content: bytes, filename: str)` et `links_in_column(rows, index)` dans `backend/app/services/sheet_source.py` — identifiants en anglais (Principe I) ; `openpyxl` en `read_only=True, data_only=True`
- [X] T038 [US2] Réécrire `parse_sheet_csv` comme appelant de ces deux fonctions, en conservant `LINK_HEADER` et l'index 9 comme **défauts de la commande CLI** — `uv run pytest tests/test_services -q` et `tests/test_cli` restent verts, la CLI ne change pas de comportement

### Routes

- [X] T039 [US2] Écrire dans `backend/tests/test_api/test_admin_batches.py` les cas de `POST /admin/sheets/columns` — colonnes rendues avec `link_count` et trois échantillons, `suggested_index` sur la colonne la plus fournie, `null` quand aucune ne porte de lien
- [X] T040 [US2] Écrire les cinq refus de `POST /admin/batches/from-file` — extension inconnue (422), > 2 Mo (413), colonne hors bornes (422), colonne sans lien exploitable (422), > 500 URL après dédoublonnage (422) ; chacun avec **son** message
- [X] T041 [US2] Écrire dans `backend/tests/test_api/test_admin_batches.py` le test de **non-écriture disque** du chemin de téléversement (SC-005) — aucune ouverture de fichier applicative pendant le traitement d'un envoi ; c'est la seule preuve vérifiable de FR-011, la plateforme n'offrant pas de shell
- [X] T042 [US2] Ajouter `SheetColumns` et `ColumnPreview` à `backend/app/schemas/batch_run.py`
- [X] T043 [US2] Implémenter `POST /admin/sheets/columns` et `POST /admin/batches/from-file` dans `backend/app/api/v1/admin_batches.py` — taille comptée **à la lecture par morceaux**, jamais d'après `Content-Length` (D9)
- [X] T044 [US2] Ajouter l'entrée `urls` au `workflow_dispatch` de `.github/workflows/batch.yml` et la branche `mode: urls` qui la tube dans `rescrape-db --urls-from -` — via `env:`, jamais interpolée dans le `run:` ; re-vérifier T007

### Interface

- [X] T045 [US2] Ajouter à `frontend/lib/api/client.ts` un envoi **multipart** distinct de `request()` — ce dernier pose `Content-Type: application/json` sur toutes les requêtes et empêcherait le navigateur d'écrire la frontière (D14) — puis `readSheetColumns` et `launchBatchFromFile`
- [X] T046 [US2] Écrire `frontend/components/admin/SheetUpload.test.tsx` — deux temps (téléverser → désigner), colonne présélectionnée, lancement désactivé tant qu'aucune colonne n'est retenue, épreuves et liens écartés annoncés avant lancement, refus affichés avec leur motif
- [X] T047 [US2] Créer `frontend/components/admin/SheetUpload.tsx` — le fichier reste dans le navigateur entre les deux appels (FR-011)
- [X] T048 [US2] Brancher `SheetUpload` dans `frontend/app/admin/batches/page.tsx`, puis vérifier `npm test` et `npm run build` depuis `frontend/`

**Checkpoint**: US2 livrable — le Google Sheet cesse d'être une source côté interface.

## Phase 6: User Story 3 — Reprise périodique (P3)

**Goal**: les résultats se rafraîchissent sans qu'on le demande.

**Independent Test**: quickstart §12, puis SC-007 en suivi différé.

- [X] T049 [US3] Ajouter le déclencheur `schedule` à `.github/workflows/batch.yml` (hebdomadaire de nuit) et le rendre compatible avec les entrées par défaut du mode `rescrape`
- [X] T050 [US3] Documenter dans `docs/ci-cd.md` la cadence retenue, **et** que GitHub désactive les workflows planifiés d'un dépôt inactif depuis 60 jours (D13) — une planification muette est une panne invisible
- [ ] T051 [US3] Constater le **destinataire réel** de la notification d'échec d'une exécution planifiée et l'écrire dans `docs/ci-cd.md` (quickstart §12) — la plateforme notifie par défaut l'auteur de la dernière modification du cron, pas l'équipe ; si ce n'est pas la bonne personne, rouvrir l'hypothèse « aucun canal d'alerte nouveau » de la spec plutôt que de vivre avec

## Phase 7: Polish & Cross-Cutting

- [X] T052 [P] Compléter `docs/ci-cd.md` — le jeton fine-grained (portée `actions: write`, dépôt seul), son expiration et sa régénération, et le **repli sans interface** (onglet Actions → « Run workflow ») exigé par FR-020
- [X] T053 [P] Mettre à jour `backend/app/cli/AGENTS.md` — où tournent désormais les batches, et ce que le workflow attend des codes de sortie
- [X] T054 [P] Mettre à jour `README.md` — la voie de lancement en production
- [ ] T055 Exécuter `specs/20260806-143754-ops-batch-runs/quickstart.md` §8 à §12 — lancement depuis l'interface, refus du second lancement, import réel d'un fichier du club, absence de dégradation du site public pendant le batch (SC-004), et les deux faces de l'alerte (échec total rouge, échec partiel vert)
- [ ] T056 Ouvrir la **PR 2** avec `Closes #47` — mot-clé anglais, seul reconnu par GitHub (AGENTS.md)
- [ ] T057 Poser un rappel de suivi à J+30 après activation de la planification pour SC-007 (quatre échéances consécutives sans intervention) — hors critère de fusion, mais c'est ce qui révélerait une planification silencieusement désactivée

---

## Dépendances

```text
PR 1 ─ Phase 1 (Setup) ─► Phase 2 (workflow) ─► T009 merge ─► T010 quickstart §7
                                                                     │
                                                                     ▼  (bloquant)
PR 2 ─ Phase 3 (client) ─► Phase 4 — US1 (P1) ──► MVP
                                   ├─► Phase 5 — US2 (P2)
                                   └─► Phase 6 — US3 (P3)
                                              └─► Phase 7 (Polish)
```

- **T010 est un point de passage obligé.** Elle valide que la base est joignable
  depuis un runner (D12). La franchir en supposant qu'elle passera revient à
  construire l'API et l'écran sur une hypothèse non vérifiée.
- **US2 dépend d'US1** pour tout l'aval : dispatch, suivi, bilan. Elle n'ajoute
  qu'une façon de produire la liste d'épreuves.
- **US3 dépend d'US1** au sens du bon sens, pas du code : planifier une exécution
  dont on n'a jamais vu aboutir une occurrence est un pari.
- **T019 laisse volontairement la suite rouge** jusqu'à T023 — c'est le cycle
  rouge/vert, pas un oubli (D10).

## Parallélisation

- **Phase 1** : T001 et T002 en parallèle (fichiers distincts).
- **Phase 4** : T026 et T028 en parallèle du backend une fois T023 posé ; T029 et T031 en parallèle l'un de l'autre.
- **Phase 5** : T035 et T036 s'écrivent ensemble (même fichier, un seul auteur) ; T045 est indépendant du backend une fois le contrat figé.
- **Phase 7** : T052, T053 et T054 en parallèle.

Les tâches de test et l'implémentation qu'elles décrivent ne sont **jamais**
parallèles : c'est l'ordre qui fait le TDD.

## Stratégie de livraison

1. **PR 1 (T001-T010)** — le workflow devient déclenchable, et le repli de FR-020
   existe. Petite, relisible, et elle purge le risque d'infrastructure.
2. **MVP = Phases 3 + 4** — un administrateur lance une reprise et lit son bilan
   sans terminal : l'objet de #47 est atteint.
3. **US2** ensuite, qui remplace le Google Sheet par un fichier choisi.
4. **US3** en dernier, une fois qu'une exécution réelle a prouvé qu'elle aboutit.

Aucune phase ne laisse le dépôt avec une suite de tests rouge, **sauf entre T019
et T023**, où c'est le cycle TDD qui l'exige.

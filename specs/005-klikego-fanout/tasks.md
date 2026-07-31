---
description: "Task list — Fan-out des heats Klikego"
---

# Tasks: Fan-out des heats Klikego

**Input**: Design documents from `specs/005-klikego-fanout/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/klikego-fanout.md](./contracts/klikego-fanout.md).

**Tests**: Le Principe III de la constitution v1.0.0 est **non-négociable** — TDD sans réseau. Toutes les tâches de test précèdent leur implémentation dans chaque user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : tâche parallélisable (fichier distinct, aucune dépendance non résolue).
- **[Story]** : US1 / US2 / US3 (mapping vers `spec.md`).
- Chemins toujours absolus par rapport à la racine du dépôt.

## Path Conventions

- **Backend** : `backend/app/`, `backend/tests/`.
- **Frontend** : `frontend/components/`, `frontend/hooks/`, `frontend/app/`.
- Structure choisie dans `plan.md` §Project Structure.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose** : préparer les fixtures HTML nécessaires aux tests unitaires offline, avant qu'aucune tâche métier ne commence.

- [X] T001 [P] Capturer `mesquer-2026-event.html` depuis `GET https://www.klikego.com/resultats/triathlon-et-swimrun-mesquer-quimiac-2026/1677015306084-12` (curl une seule fois, puis débrancher), le minifier à ~20 Ko en gardant intact le bloc `<el-select name="heat">…</el-select>` avec ses 8 `<el-option>`, le commiter dans `backend/tests/fixtures/klikego/mesquer-2026-event.html`.
- [X] T002 [P] Capturer `mesquer-2026-heat-swimrun-m.html` depuis la même URL avec `?heat=swim-run-m-duo`, minifier à l'essentiel (page de heat suffisante pour `_parse_detail`), commit dans `backend/tests/fixtures/klikego/mesquer-2026-heat-swimrun-m.html`.
- [X] T003 [P] Capturer `nozeen-2025-no-select.html` depuis `https://www.klikego.com/resultats/5e-duathlon-nozeen-2025/1517534975128-7` (page sans `<el-select name="heat">`), minifier, commit dans `backend/tests/fixtures/klikego/nozeen-2025-no-select.html`.
- [X] T004 Ajouter dans `backend/tests/conftest.py` un helper `load_klikego_fixture(name: str) -> str` qui lit `backend/tests/fixtures/klikego/{name}` via `pathlib.Path(__file__).parent`, utilisé par tous les tests de la feature. Aucune configuration `pytest` nécessaire — les `.html` sont lus à runtime.

**Checkpoint** : les 3 fixtures HTML existent, le helper `load_klikego_fixture` est disponible.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose** : le fan-out lui-même est le seul prérequis structurel — sans la boucle interne du scraper, aucune user story ne peut fonctionner. On isole ici la fonction d'énumération, réutilisée par toutes les user stories.

**⚠️ CRITICAL** : aucune US ne démarre tant que T007 et T007b ne sont pas vertes.

- [X] T005 [P] Écrire `backend/tests/test_klikego.py::test_enumerate_heats_mesquer` — charge `mesquer-2026-event.html` depuis les fixtures, assert que `_enumerate_heats(html)` renvoie **8 tuples** dans l'ordre du DOM, dont `("triathlon-s-indiv", "Triathlon S Indiv")` et `("swim-run-m-duo", "Swim Run M Duo")`. Test doit échouer (fonction pas encore créée).
- [X] T006 [P] Écrire `backend/tests/test_klikego.py::test_enumerate_heats_no_select` — charge `nozeen-2025-no-select.html`, assert que `_enumerate_heats(html) == []`. Écrire aussi `test_enumerate_heats_empty_string` et `test_enumerate_heats_select_without_options` (HTML minimal inline), assert `[]` sur les deux. Tests doivent tous échouer.
- [X] T007 Implémenter `_enumerate_heats(html: str) -> list[tuple[str, str]]` dans `backend/app/scrapers/klikego.py` selon C1 (regex `_RE_SELECT` + `_RE_OPTION`). Les tests T005/T006 doivent passer.
- [X] T007a [P] Écrire `backend/tests/test_registry.py::test_get_provider_returns_instance` — pour chaque URL exemple (klikego, breizhchrono, `live.breizhchrono.com`, wiclax, github.com, `https://[oops`), assert que `registry.get_provider(url)` rend soit l'instance de la classe attendue, soit `None`. Aucun test ne doit lever. Test doit échouer (fonction pas encore créée).
- [X] T007b Implémenter `registry.get_provider(url: str) -> Provider | None` dans `backend/app/scrapers/registry.py` selon C6 : itère sur `PROVIDERS`, rend la première instance dont `matches(url)` est vrai, `None` sinon. Test T007a doit passer.

**Checkpoint** : `_enumerate_heats` et `get_provider` existent, leurs tests unitaires sont verts, aucune régression sur `test_klikego.py` ni `test_registry.py`.

---

## Phase 3: User Story 1 — Import complet d'un événement multi-épreuves (Priority: P1) 🎯 MVP

**Goal** : coller une URL Klikego (nue ou `?heat=X`) dans `/ajouter` importe **tous** les heats publiés de l'événement (contrat C2, arbitrages A1 et A4). Le bilan (SSE + CLI) porte les 4 compteurs `heats_enumerated`/`imported`/`cached`/`failed` + `failures[]` (FR-008, contrat C4).

**Independent Test** : cf. `quickstart.md` Vérif 2 (URL nue) et Vérif 3 (URL `?heat=`). Attendu : 8 courses Mesquer créées, chacune avec sa `source_url` distincte et son `event_type` correct ; sur un heat en échec, `heats_failed=1` et `failures[]` non vide dans le SSE `done`.

### Tests for User Story 1

- [X] T008 [P] [US1] Écrire `backend/tests/test_klikego.py::test_scrape_event_all_fanout_nominal` — monkeypatch `httpx.Client.get` pour qu'il rende `mesquer-2026-event.html` sur la page événement et `mesquer-2026-heat-swimrun-m.html` sur chaque page de heat, appeler `klikego.scrape_event_all(event_id="1677015306084-12", heat="", event_name="Mesquer", slug="triathlon-et-swimrun-mesquer-quimiac-2026")` **sans** passer `cache_probe` (défaut `None`). Assert que la fonction retourne un tuple `(results, trace)` — cf. contrat C2 étendu — dont `results` contient des `ScrapedResult` couvrant les 8 `heat_slug` distincts, chacun avec un `event_type` classifié conforme au fix #154 (`triathlon-s`, `swimrun-m`, etc.), et `trace == FanoutTrace(heats_enumerated=8, heats_cached=0, heats_imported=0, failures=[])`.
- [X] T008a [P] [US1] Écrire `backend/tests/test_klikego.py::test_scrape_event_all_fanout_cache_probe` — même setup que T008, appeler avec `cache_probe=lambda heat_url: "swim-run-m-duo" in heat_url or "triathlon-xs-indiv" in heat_url` (2 heats sur 8). Assert que `results` contient **6** `ScrapedResult` (les non-cachés), `trace.heats_cached == 2`, `trace.heats_enumerated == 8`, `trace.failures == []`. Vérifier via un compteur de mocks que le scrape des 2 heats cachés n'a **pas** été appelé.
- [X] T009 [P] [US1] Écrire `backend/tests/test_klikego.py::test_scrape_event_all_fanout_ignores_query_heat` — même setup, mais appeler avec un `?heat=X` implicite via l'URL passée en amont ; assert que **tous** les heats sont scrapés, pas seulement celui du query. (Le test opère au niveau du provider `KlikegoProvider.scrape_event_all(url)`, pas de la fonction module — cf. T011.)
- [X] T010 [P] [US1] Écrire `backend/tests/test_klikego.py::test_scrape_event_all_fanout_heat_failure_isolated` — monkeypatch qui fait lever `httpx.HTTPError` dans le scrape d'**un** des 8 heats, assert que la fonction rend un tuple dont `results` contient les **7** autres heats et `trace.failures == [{"heat_slug": "<slug>", "reason": "<str(exc)>"}]`. `logger.warning` capturé via `caplog`. Aucune exception ne remonte.
- [X] T011 [P] [US1] Écrire `backend/tests/test_registry.py::test_klikego_provider_ignores_query_heat` — instancier `KlikegoProvider()`, appeler `scrape_event_all("https://…/1677015306084-12?heat=triathlon-s-indiv")` (avec les mêmes monkeypatchs), assert que le résultat contient **8 heats**, pas 1. `parsed.query["heat"]` doit être ignoré côté provider.
- [X] T012 [P] [US1] Écrire `backend/tests/test_registry.py::test_klikego_provider_stores_last_trace` — après un appel `scrape_event_all("https://…/1677015306084-12")` (mocké avec 1 heat en échec sur 8), assert que `provider.last_trace.heats_enumerated == 8` et `provider.last_trace.failures` contient 1 entrée avec `heat_slug` + `reason`. `last_trace` est réinitialisé à chaque appel (deux appels successifs ne cumulent pas les failures).
- [X] T013 [P] [US1] Écrire `backend/tests/test_services/test_import_service.py::test_iter_import_event_exposes_fanout_counters` — préparer une base de test avec 2 `Course` déjà créées sur des heats de Mesquer et fraîches côté cache TTL. Appeler `iter_import_event` sur un événement Mesquer mocké (8 heats à la source, 1 en échec au scrape) — l'`import_service` construit et injecte `cache_probe` qui probe `services.cache.is_fresh` heat par heat, donc les 2 heats en base sont sautés par le scraper. Consommer les phases jusqu'à `done`. Assert que le dict `done` porte exactement `heats_enumerated=8`, `heats_imported=5`, `heats_cached=2`, `heats_failed=1`, `failures=[{"heat_slug": …, "reason": …}]`, invariant `enumerated == imported + cached + failed`.
- [X] T014 [P] [US1] Écrire `frontend/components/scrape/ImportProgress.test.tsx::renders_courses_on_done` — 3 cas de figure : `state.courses = []` (rendu identique à aujourd'hui, aucun lien), `state.courses = [1 elem]` (message + 1 `<Link>` vers `/courses/<id>`), `state.courses = [8 elems]` (message + 8 liens, ordre stable). Assert présence des `href="/courses/{id}"` et du libellé de course.
- [X] T015 [P] [US1] Écrire `frontend/components/scrape/ImportProgress.test.tsx::renders_failures_when_present` — `state.phase = "done"`, `state.failures = [{heat_slug: "…", reason: "…"}]` (2 entrées), assert présence d'un bloc « Heats en erreur » sous le récap des courses, listant chaque paire `slug`/`reason`. Cas `state.failures = []` ou `undefined` → aucun bloc rendu (pas de « 0 erreur » affiché).

### Implementation for User Story 1

- [X] T016 [US1] Refactoriser `klikego.scrape_event_all(event_id, heat, event_name, slug, *, cache_probe=None) -> tuple[list[ScrapedResult], FanoutTrace]` dans `backend/app/scrapers/klikego.py`. Définir le dataclass `FanoutTrace(heats_enumerated: int, heats_cached: int, heats_imported: int, failures: list[dict])` (heats_imported laissé à 0 côté scraper ; dérivé en aval par `import_service`). Corps : si `heat` est vide, GET la page événement, `_enumerate_heats(html)` alimente `trace.heats_enumerated`. Boucler sur `(heat_slug, heat_label)` :
  - construire `heat_url = f"{BASE}/resultats/{slug}/{event_id}?heat={heat_slug}"` ;
  - si `cache_probe is not None and cache_probe(heat_url)` : `trace.heats_cached += 1`, `continue` (sans scraper) ;
  - sinon scraper le heat via l'ancien chemin, appender au `results`. Sur exception : `trace.failures.append({"heat_slug": heat_slug, "reason": str(exc)})` + `logger.warning("Heat %s de %s en échec : %s", heat_slug, event_id, exc)`.
  Si `_enumerate_heats` rend `[]`, retour `([], FanoutTrace(0, 0, 0, []))`. Si `heat` est renseigné (single-heat), scraper ce seul heat sans consulter `cache_probe`. Tests T005/T008/T008a/T010 doivent passer.
- [X] T017 [US1] Modifier `KlikegoProvider.scrape_event_all(url, *, cache_probe=None)` dans `backend/app/scrapers/registry.py` : supprimer la lecture de `params.get("heat", …)` et la pré-résolution `_detect_heat` ; appeler `results, trace = klikego.scrape_event_all(event_id, heat="", event_name, slug, cache_probe=cache_probe)` ; stocker `self.last_trace = trace` (initialisé à `None` sur l'instance provider) ; retourner uniquement `results` pour préserver le contrat plat vis-à-vis du registre. Adapter le Protocol `Provider.scrape_event_all(url, **kwargs)` pour accepter le kwarg côté interface — les autres providers l'ignorent. Tests T009/T011/T012 doivent passer.
- [X] T017a [US1] Modifier `backend/app/services/import_service.py::_scrape_all(url, *, cache_probe=None)` pour propager le kwarg au provider via `registry_scrape_event_all(url, cache_probe=cache_probe)`. Adapter la signature dans `registry.py::scrape_event_all` (dispatch de niveau module) : accepter `**kwargs` et les passer au provider matché.
- [X] T018 [US1] Modifier `backend/app/services/import_service.py::iter_import_event` et `import_event` :
  1. Construire `cache_probe = lambda heat_url: (course := course_repository.get_by_source_url(db, heat_url)) is not None and cache.is_fresh(course)` (protégé par le settings TTL déjà en place).
  2. Passer `cache_probe` à `_scrape_all(url, cache_probe=cache_probe)`.
  3. Après `_scrape_all`, récupérer l'instance provider via `registry.get_provider(url)` (introduit en T007b) et lire `provider.last_trace`. Défaut si `None` (provider non-Klikego) : `FanoutTrace(1, 0, 1, [])` sur succès, `FanoutTrace(0, 0, 0, [])` sur `ScraperError`.
  4. Calculer `heats_failed = len(trace.failures)` et `heats_imported = trace.heats_enumerated - trace.heats_cached - heats_failed` (invariant).
  5. Injecter les 5 clés (`heats_enumerated`, `heats_imported`, `heats_cached`, `heats_failed`, `failures`) dans le dict de la phase `done` et dans le retour de `import_event()`. Vérifier l'invariant sur chaque chemin de sortie (cache TTL global frais → 0/0/0/[], aucun résultat → 0/0/0/[], done nominal).
  Test T013 doit passer.
- [X] T019 [US1] Modifier `frontend/hooks/useImportStream.ts` : étendre `ImportState` avec `heatsEnumerated?: number`, `heatsImported?: number`, `heatsCached?: number`, `heatsFailed?: number`, `failures?: {heat_slug: string; reason: string}[]` (optionnels côté type, remplis en phase `done`). Modifier `frontend/components/scrape/ImportProgress.tsx` : à la phase `done`, (a) si `state.courses.length > 0`, rendre sous le message existant une liste de `<Link href={`/courses/${c.id}`}>…</Link>` avec un chip `FormatChip` sur `c.event_type` (import depuis `@/components/tcn`), avec un titre au singulier ou pluriel (« 1 course importée » / « N courses importées ») ; (b) si `state.failures?.length > 0`, rendre sous les courses un bloc « Heats en erreur » listant `{heat_slug} : {reason}` un par ligne. Tests T014 et T015 doivent passer.

**Checkpoint** : les 8 tests d'US1 sont verts. Vérif manuelle possible selon `quickstart.md` Vérif 2 et 3 après lancement des services de dev. Contrat SSE `done` étendu de 5 clés rétro-compatibles.

---

## Phase 4: User Story 3 — Import CLI de masse (Priority: P2a) — traité avant US2 (P2b)

**Note d'ordre (I1)** : les deux user stories P2 sont ordonnées P2a (US3, import de masse) puis P2b (US2, ré-import avec cache). Justification technique : US3 sanctionne le contrat CLI existant sans ajouter de code, US2 s'appuie sur les compteurs `heats_cached` introduits par US1 et devient triviale une fois US3 vérifiée. Cet ordonnancement diverge délibérément de l'ordre de la spec (US1/US2/US3) et est consigné ici pour éviter toute confusion à la lecture.

**Goal** : `import-sheet` (chemin nominal) traite toute URL Klikego comme « événement entier », cohérent avec l'UI. Aucune option nouvelle sur `import-sheet` (contrat C3, non-goal explicite).

**Independent Test** : cf. `quickstart.md` Vérif 5 — `import-sheet --dry-run --limit 3` annonce le bon nombre d'épreuves à traiter, incluant le fan-out sur URLs nues.

### Tests for User Story 3

- [X] T020 [P] [US3] Écrire `backend/tests/test_cli/test_import_sheet.py::test_dry_run_reports_fanout_count` — monkeypatch `sheet_source.download_csv` pour rendre un CSV inline avec 2 URLs Klikego (l'une nue Mesquer, l'autre `?heat=` sur le même événement), monkeypatch `registry.scrape_event_all` pour rendre 8 `ScrapedResult` avec `event_type` distincts par appel, invoquer `import-sheet --dry-run` via Typer's `CliRunner`. Assert que le bilan annonce **8 épreuves** (pas 2 ni 16 — l'un des deux imports doit être court-circuité par cache TTL ou dédoublonnage d'URL, comportement à valider).
- [X] T021 [P] [US3] Écrire `backend/tests/test_cli/test_import_sheet.py::test_stdout_stays_parseable` — vérifie que la progression reste sur stderr et que `--json | jq` peut parser stdout (contrat CLI existant, non-régression après refacto).

### Implementation for User Story 3

- [X] T022 [US3] Aucun code à modifier côté `import-sheet` — le fan-out se produit dans `KlikegoProvider.scrape_event_all` déjà refactorisé en T017. Cette tâche consiste à **exécuter** les tests T020/T021 et à valider qu'ils passent sans changement dans `backend/app/cli/commands/import_sheet.py` ni `backend/app/services/batch.py`. Si un test échoue par régression (par ex. dédoublonnage cassé), ouvrir un ticket dédié — hors périmètre du fan-out.

**Checkpoint** : US1 + US3 fonctionnels. L'import de masse et l'UI sont cohérents (une URL Klikego = tous les heats, quelle que soit l'entrée).

---

## Phase 5: User Story 2 — Ré-import d'un événement partiellement en base (Priority: P2)

**Goal** : recoller une URL Klikego déjà partiellement importée détecte les heats déjà en cache et ne re-scrape que les nouveaux (FR-005, SC-005).

**Independent Test** : après un premier import de Mesquer (Phase 3), recoller la même URL. Bilan attendu : « 0 imported, 0 updated, 8 skipped » (ou l'équivalent SSE `done`), et le nombre de requêtes HTTP faites doit être proportionnel au nombre de heats **non** en cache.

### Tests for User Story 2

- [X] T023 [P] [US2] Écrire `backend/tests/test_services/test_import_service.py::test_reimport_hits_cache_per_heat` — préparer une base de test avec 3 `Course` déjà créées sur 3 heats de Mesquer, monkeypatch pour rendre `mesquer-2026-event.html` (8 heats à la source), invoquer `import_event(db, mesquer_url, settings)`. Assert :
  1. Le résultat contient 8 `Course` dans `courses[]` (les 3 existantes récupérées via cache TTL + 5 nouvelles scrapées).
  2. Le nombre de fois où `_parse_detail` (ou une fonction interne du scraper de heat) est appelé est **5**, pas 8 — le cache par heat a court-circuité.
  3. Le bilan porte `heats_enumerated=8`, `heats_cached=3`, `heats_imported=5`, `heats_failed=0`.
- [X] T024 [P] [US2] Écrire `backend/tests/test_klikego.py::test_scrape_event_all_respects_cache_per_heat` — variante unitaire du même invariant côté scraper, si la mécanique de cache peut être testée à ce niveau (`_cached_result` vit dans `import_service`, mais le contrat de non-appel de `_parse_detail` est vérifiable via monkeypatch).

### Implementation for User Story 2

- [X] T025 [US2] Aucun code à modifier — le cache TTL par heat est déjà en place (`services/cache.py::is_fresh`) et fonctionne au niveau de `Course.source_url` qui reste au niveau du heat (cf. `data-model.md`). Cette tâche consiste à exécuter T023/T024 et à documenter le résultat dans un commit « test(import): couvre le cache par heat après fan-out (US2) ». Si un test échoue, investiguer si le cache TTL a besoin d'une adaptation (mais aucun changement n'est prévu par le plan).

**Checkpoint** : US1 + US2 + US3 tous verts. Les 3 user stories sont indépendamment testables et livrables.

---

## Phase 6: Échappatoire `--single-heat` + bilan CLI enrichi (transverse)

**Note** : la phase groupe deux préoccupations CLI :
- L'échappatoire `--single-heat` (contrat C3, A3 / FR-007a) — cas de bord pour importer un heat unique.
- L'extension du bilan CLI aux 5 compteurs de fan-out (contrat C3 §Bilan CLI enrichi + contrat C4 côté SSE) — mise en cohérence de `reports.py` avec le SSE `done`.

Ce n'est pas une user story de la spec ; elle est en Phase 6 (transverse, sans label `[US*]`).

**Goal** : `rescrape-db --url "…?heat=X" --single-heat` importe **uniquement** le heat X, sans fan-out (contrat C3).

**Independent Test** : cf. `quickstart.md` Vérif 4.

### Tests for `--single-heat`

- [X] T026 [P] Écrire `backend/tests/test_cli/test_rescrape_db.py::test_single_heat_bypasses_fanout` — via Typer's `CliRunner`, appeler `rescrape-db --url "https://…?heat=triathlon-s-indiv" --single-heat`, monkeypatch `registry.scrape_event_all` pour distinguer chemin single-heat vs fan-out. Assert que le scraper est appelé en mode single-heat (une seule `Course` scrapée).
- [X] T027 [P] Écrire `backend/tests/test_cli/test_rescrape_db.py::test_single_heat_requires_url_with_heat` — cas d'erreur d'usage : `--single-heat` sans `--url`, `--single-heat` avec URL nue, `--single-heat` combiné à `--provider`. Assert exit code 2 et message qui nomme la contrainte pour chaque.
- [X] T028 [P] Écrire `backend/tests/test_cli/test_rescrape_db.py::test_single_heat_multiple_urls` — `--url A?heat=X --url B?heat=Y --single-heat` : 2 scrapes en mode single-heat, chacun sur son heat. Assert bilan à 2 épreuves ciblées, 0 fan-out.
- [X] T029 [P] Écrire `backend/tests/test_cli/test_reports.py::test_reports_render_fanout_failures` — appeler la fonction de rendu du bilan avec un `BatchOutcome` (ou équivalent) qui porte `heats_enumerated=8, heats_imported=5, heats_cached=2, heats_failed=1, failures=[{"heat_slug": "…", "reason": "…"}]`. Assert que la sortie texte contient un bloc « Heats en erreur (détail) : » listant `slug: reason`, et que la charge `--json` porte les 5 clés au niveau du bilan par épreuve et aux agrégats du batch.

### Implementation for `--single-heat`

- [X] T030 Ajouter dans `backend/app/scrapers/registry.py::KlikegoProvider` un chemin « single_heat » (soit via `scrape_event_all_single_heat(url)`, soit via un flag interne au provider). Fanout est le défaut ; single_heat = lit `?heat=X` de l'URL et court-circuite `_enumerate_heats`. `last_trace` reste rempli en mode single-heat (`heats_enumerated=1`, `failures=[]` en succès). Test T026 doit passer.
- [X] T031 Ajouter l'option Typer `--single-heat` dans `backend/app/cli/commands/rescrape_db.py`, la câbler à un paramètre de `rescrape_service` qui appellera le chemin single_heat du provider Klikego. Validation d'usage dans `backend/app/cli/validators.py` (ou équivalent) : rejeter les combinaisons invalides avant tout scraping (code 2). Tests T027/T028 doivent passer.
- [X] T032 Ajouter une clause dans `backend/app/services/rescrape_service.py` (ou équivalent selon la structure existante) pour propager le flag `single_heat` du CLI jusqu'à l'appel du provider. Vérifier que le comportement est **stateless** — un batch mixte de N URLs avec `--single-heat` n'affecte pas l'ordre de traitement, chaque URL a son propre chemin.
- [X] T033 Étendre le rendu texte du bilan `rescrape-db` (et par cohérence `import-sheet`) dans `backend/app/cli/reports.py` pour afficher un bloc « Heats en erreur (détail) : » listant `{heat_slug}: {reason}`, alimenté par `failures[]`. Aligner la charge `--json` : ajouter `heats_enumerated`/`heats_imported`/`heats_cached`/`heats_failed`/`failures` par épreuve et agrégés au niveau batch. Test T029 doit passer.

**Checkpoint** : `--single-heat` fonctionne, les 3 tests passent, le chemin nominal (sans `--single-heat`) reste inchangé.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T034 [P] Vérifier via `git diff main..HEAD -- backend/alembic/versions/` qu'**aucune** nouvelle révision Alembic n'a été introduite (contrat de `data-model.md` §Migration). Si présence : investigation et suppression.
- [X] T035 [P] Lancer `uv run ruff check .` dans `backend/`, corriger les warnings introduits par la feature. Aucun `# noqa` ajouté sans justification en commentaire.
- [X] T036 [P] Lancer `uv run pytest -m "not integration" -q` en entier — assert que la baseline de 1675+ tests passe, plus les tests nouveaux de la feature. Aucun test flaky introduit. **G2 — non-régression BC / Wiclax / T2Area** : la suite existante contient déjà des tests d'intégration mock pour ces providers (`test_breizhchrono.py`, `test_wiclax.py`, `test_t2area.py`) — leur passage sans modification confirme que l'élargissement du Protocol `Provider.scrape_event_all(url, **kwargs)` est bien rétro-compatible (le `cache_probe=…` transmis par `import_service` est reçu et ignoré silencieusement).
- [X] T037 [P] Lancer `npm test` puis `npm run build` dans `frontend/` — Vitest vert (tests T014/T015 inclus), build prod compile en strict TS.
- [X] T038 Dérouler manuellement `quickstart.md` §Vérifications 2 à 7 avec les services de dev lancés (`uv run python scripts/dev_server.py` et `npm run dev`). Consigner tout écart entre attendu et observé.
- [X] T039 Mettre à jour la section « Fournisseurs supportés » de `AGENTS.md` pour mentionner explicitement : « Klikego : URL = événement entier (fan-out sur tous les heats du `<el-select>`). Une URL avec `?heat=` importe l'événement entier — le paramètre est ignoré. Échappatoire : `rescrape-db --url "…?heat=X" --single-heat`. Le SSE `done` et le bilan CLI portent `heats_enumerated`/`heats_imported`/`heats_cached`/`heats_failed`/`failures[]`. Symétrie avec Breizh Chrono qui fan-outait déjà (sans compteurs). »

**Checkpoint** : feature prête pour `requesting-code-review`.

---

## Dependencies

**Phase 1 (Setup)** — T001, T002, T003 en parallèle ; T004 après les 3.

**Phase 2 (Foundational)** — bloque toutes les user stories. T005/T006/T007a en parallèle, puis T007 (impl `_enumerate_heats`) et T007b (impl `get_provider`) en parallèle.

**Phase 3 (US1 — MVP)** — dépend de Phase 2 (`get_provider` et `_enumerate_heats` requis). Tests écrits d'abord (T008/T008a/T009-T015 en parallèle, fichiers distincts) → impl : T016 (klikego module, `FanoutTrace` + `cache_probe`) → T017 (provider, `last_trace`, kwarg `cache_probe`) → T017a (`_scrape_all` propage `cache_probe`) → T018 (`import_service`, construit `cache_probe`, injecte compteurs) ; T019 (front, hooks + rendu) en parallèle des impl backend une fois le contrat SSE fixé.

**Phase 4 (US3)** — dépend de US1 (T017 en particulier). T020/T021 en parallèle, T022 en dernier.

**Phase 5 (US2)** — dépend de US1. T023/T024 en parallèle, T025 valide.

**Phase 6 (--single-heat + CLI reports)** — dépend de US1. Tests T026/T027/T028/T029 en parallèle → impl : T030 (provider single-heat) → T031 (CLI options + validators) → T032 (rescrape_service) → T033 (CLI reports — dépend de T018 pour la source des compteurs).

**Phase 7 (Polish)** — dépend de tout le reste. T034/T035/T036/T037 en parallèle, T038/T039 après.

## Parallel Opportunities

- **Fixtures HTML (T001/T002/T003)** : 3 captures indépendantes.
- **Tests d'US1 (T008/T009/T010/T011/T012/T013/T014/T015)** : 8 tests, dans 4 fichiers distincts (`test_klikego.py`, `test_registry.py`, `test_services/test_import_service.py`, `ImportProgress.test.tsx`) → parallélisables à l'écriture, `pytest` sérialise à l'exécution.
- **Tests de `--single-heat` + CLI reports (T026-T029)** : dans `test_rescrape_db.py` et `test_reports.py`.
- **Polish (T034-T037)** : 4 vérifications indépendantes.

## Independent Test Criteria Recap

- **US1** : coller une URL Klikego (nue ou `?heat=`) dans `/ajouter` → N courses créées, récap affiché, chaque course accessible via `/courses/<id>`.
- **US2** : recoller la même URL → « 0 imported, N skipped », log/monitoring confirme que le cache TTL a court-circuité les heats déjà en base.
- **US3** : `import-sheet --dry-run` → bilan cohérent avec le fan-out (nombre d'épreuves à traiter reflète l'énumération réelle).
- **`--single-heat`** : `rescrape-db --url "…?heat=X" --single-heat` → 1 course, pas N.

## MVP Scope

**MVP = US1 seule** (Phase 3, `quickstart.md` Vérif 2 et 3). C'est l'objectif principal de l'issue #156 : coller une URL Klikego et obtenir toutes les épreuves de l'événement. US2, US3 et `--single-heat` renforcent le contrat mais US1 seule est livrable.

## Format validation

- ✅ Chaque tâche commence par `- [ ]`.
- ✅ Chaque tâche a un ID unique (T001 → T039, plus T007a/T007b/T008a/T017a insérés pour éviter la renumérotation en cascade).
- ✅ `[P]` sur les tâches parallélisables (fichiers distincts, pas de dépendance interne à la phase).
- ✅ `[US1]`/`[US2]`/`[US3]` sur toutes les tâches de user story ; pas de label sur Setup, Foundational, Phase 6 (transverse), Polish.
- ✅ Chaque tâche indique un chemin de fichier explicite.
- ✅ Tests écrits **avant** l'implémentation dans chaque user story (Principe III non-négociable).

# Batch backlog B (2026-10-06) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: the user names the executor (superpowers:executing-plans or superpowers:subagent-driven-development). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer #1186, #1193, #1191, #1212, #1206, #1202 et #1209 dans une seule branche et une PR parapluie.

**Architecture:** Refactor d'abord (A : `import_service` découpé en dispatch, persistance, orchestration ; rescrape admin dans `course_rescrape_service`). Puis trois correctifs indépendants (B). Puis la règle de comptage TCN stockée dans `participations.counts_for_tcn` (C), étendue par la liste des licenciés FFTri par saison (D), sur laquelle s'appuie la séparation des homonymes (E).

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0 sync, Alembic, pytest ; Next.js 16, TypeScript, vitest.

**Spec:** `docs/superpowers/specs/2026-10-06-backlog-batch-b-design.md`

## Global Constraints

- Ordre des parties : A, B, C, D, E. Dans une partie, l'ordre des tâches.
- Git : `/usr/bin/git` en commandes simples et séparées (`add` puis `commit`), le garde du worktree refuse les formes composées. Conventional Commits en anglais. **Aucun trailer `Co-Authored-By`**.
- Tests backend : `cd backend && uv run pytest -m "not integration" <chemin>` ; suite complète en fin de partie. Lint : `cd backend && uv run ruff check .`.
- Front : `cd frontend && npm test -- <chemin>`, `npm run lint`, `npm run build` en fin de partie front.
- Migrations : `down_revision` = la tête courante (`cd backend && uv run alembic heads`), une migration par changement de modèle, vérifiée par `tests/test_migrations.py`.
- Langue : français pour l'UI, les messages affichés, les docs produit et les commentaires de règle métier ; anglais pour les identifiants, tests et commits.
- Ne jamais ponctuer une phrase par un tiret (—, –, -) dans la prose, les commentaires ou l'UI.
- Un service n'importe aucun symbole `_privé` d'un autre service (`tests/test_service_boundaries.py`). Pas de réexport de compatibilité.
- Les écarts relevés en rédaction sont notés dans chaque partie ; un écart trouvé à l'exécution se remonte à l'utilisateur.

---


# Partie A

## Part A: #1186 split `import_service` and move the admin rescrape

Pure refactor: no behaviour change. The unit suite is the safety net; each task adds a
layout test that fails before the move and passes after it.

Conventions for every task in this part:

- `SCRATCH=/tmp/claude-1000/-home-mherrmann-Documents-work-tcn-data-triathlon--claude-worktrees-backlog-batch-2026-10-06/088b5b3c-0c30-4b03-8331-26c15a3cd049/scratchpad`
  holds the one-shot helper scripts (never committed).
- Commands run from `backend/` unless stated. Git is called as `/usr/bin/git`, one plain
  command per call (the worktree guard refuses compound git commands).
- `monkeypatch.setattr(module, "name", ...)` raises `AttributeError` when `module` has no
  attribute `name` (default `raising=True`). A patch left pointing at the old module
  therefore fails loudly **as long as the old module no longer has the attribute**. The
  layout tests below assert exactly that absence: they are what turns a stale patch into
  a red test instead of a silent real scrape.

### Task A0: one-shot helper scripts

No repo change, no commit. Create the two helpers used by A1 to A3.

- [ ] **Step 1: write `$SCRATCH/move_symbols.py`**

```python
"""Move top-level symbols from one Python module to another (refactor helper, #1186).

Usage: python move_symbols.py SRC DEST DOCSTRING_FILE NAME [NAME ...]

If DEST does not exist it is created with the docstring read from DOCSTRING_FILE,
followed by SRC's whole import block (first import statement through the
`logger = logging.getLogger(__name__)` line). `ruff --fix --select F401,I001`
prunes what the destination does not use. Moved chunks keep their source order and
the comment lines directly above them.
"""
import ast
import sys
from pathlib import Path


def _name(node: ast.stmt) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def main() -> None:
    src, dest, doc_file, *names = sys.argv[1:]
    wanted = set(names)
    text = Path(src).read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)

    spans: list[tuple[int, int, str]] = []
    first_import = None
    logger_end = None
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)) and first_import is None:
            first_import = node.lineno - 1
        if _name(node) == "logger":
            logger_end = node.end_lineno
        name = _name(node)
        if name not in wanted:
            continue
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]) - 1
        while start > 0 and lines[start - 1].lstrip().startswith("#"):
            start -= 1
        spans.append((start, node.end_lineno, name))

    missing = wanted - {name for *_, name in spans}
    if missing:
        sys.exit(f"Not found in {src}: {sorted(missing)}")

    chunks = ["".join(lines[start:end]).rstrip() + "\n" for start, end, _ in spans]
    dest_path = Path(dest)
    if dest_path.exists():
        body = dest_path.read_text(encoding="utf-8").rstrip() + "\n"
    else:
        doc = Path(doc_file).read_text(encoding="utf-8").rstrip() + "\n"
        body = doc + "".join(lines[first_import:logger_end]).rstrip() + "\n"
    dest_path.write_text(body + "\n\n" + "\n\n".join(chunks), encoding="utf-8")

    kept = []
    removed = {i for start, end, _ in spans for i in range(start, end)}
    kept = [line for i, line in enumerate(lines) if i not in removed]
    cleaned = "".join(kept)
    while "\n\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n\n", "\n\n\n")
    Path(src).write_text(cleaned, encoding="utf-8")
    print(f"moved {len(spans)} symbols from {src} to {dest}")


main()
```

- [ ] **Step 2: write `$SCRATCH/rewrite.py`**

```python
"""Regex rewrites plus import fix-up over a set of files (refactor helper, #1186).

Usage: python rewrite.py RULES_MODULE FILE [FILE ...]
RULES_MODULE is a .py file defining:
  RULES: list[tuple[str, str]]          # (regex, replacement), applied in order
  ENSURE: list[tuple[str, str]]         # (new_module, anchor_module)
For each (new_module, anchor) in ENSURE, every single-line
`from app.services import ...` that already names `anchor` also gets `new_module`
when the file uses `new_module.` anywhere. `ruff --fix --select F401,I001` then
drops the anchors that became unused and re-sorts.
"""
import re
import runpy
import sys
from pathlib import Path

LINE = re.compile(r"^(?P<indent>[ \t]*)from app\.services import (?P<names>[^()\n]+)$", re.M)


def ensure(text: str, module: str, anchor: str) -> str:
    if f"{module}." not in text:
        return text

    def add(match: re.Match) -> str:
        names = [n.strip() for n in match.group("names").split(",")]
        if anchor not in names or module in names:
            return match.group(0)
        return f"{match.group('indent')}from app.services import {', '.join(sorted(names + [module]))}"

    return LINE.sub(add, text)


def main() -> None:
    rules_file, *files = sys.argv[1:]
    cfg = runpy.run_path(rules_file)
    changed = 0
    for name in files:
        path = Path(name)
        before = path.read_text(encoding="utf-8")
        text = before
        for pattern, repl in cfg["RULES"]:
            text = re.sub(pattern, repl, text)
        for module, anchor in cfg.get("ENSURE", []):
            text = ensure(text, module, anchor)
        if text != before:
            path.write_text(text, encoding="utf-8")
            changed += 1
            print(f"rewrote {name}")
    print(f"{changed} file(s) changed")


main()
```

### Task A1: extract `import_persistence`

**Files:**
- Create: `backend/app/services/import_persistence.py`
- Modify: `backend/app/services/import_service.py` (remove the persistence group, call it through the module)
- Modify: `backend/app/services/batch.py:24`, `backend/app/services/bulk_import_service.py:21`, `backend/app/services/rescrape_service.py:36`, `backend/app/services/admin_actions.py:51,465,667`
- Modify (repoint): every `tests/**/*.py` hit listed in Step 5
- Test: `backend/tests/test_services/test_import_module_layout.py` (new)

**Interfaces:**
- Produces (used by every later part): `app.services.import_persistence` with public
  `Reassignment`, `PassiveSource`, `persist_steps(db, url, results) -> Iterator[tuple[int, _Persister]]`,
  `persist_results(db, url, results) -> dict`. `_Persister` (and its method
  `_resolve_pending`), the row helpers and the five batch passes stay private inside it.
  Part F (#1209) edits `_Persister._resolve_pending` **in this file**.
- `import_service` calls `import_persistence.persist_results(...)` and
  `import_persistence.persist_steps(...)` through the module attribute, so
  `monkeypatch.setattr(import_persistence, "persist_results", ...)` reaches `import_event`.

- [ ] **Step 1: write the failing layout test** `backend/tests/test_services/test_import_module_layout.py`

```python
"""Le découpage d'`import_service` (#1186) : chaque symbole vit dans un seul module.

L'absence de l'ancien nom compte autant que la présence du nouveau :
`monkeypatch.setattr` lève sur un attribut absent, donc un test resté pointé sur
l'ancien module échoue au lieu de laisser passer le vrai scrape ou la vraie écriture.
"""
from app.services import import_persistence, import_service


def test_persistence_lives_in_import_persistence():
    assert callable(import_persistence.persist_steps)
    assert callable(import_persistence.persist_results)
    assert import_persistence.PassiveSource.__name__ == "PassiveSource"
    assert import_persistence.Reassignment.__name__ == "Reassignment"
    for name in (
        "persist_steps", "persist_results", "PassiveSource", "Reassignment",
        "_Persister", "_TRANCHE_SIZE", "split_relay_teammates", "mapping",
    ):
        assert not hasattr(import_service, name), name
```

- [ ] **Step 2: run it, expect FAIL**

Run: `uv run pytest -m "not integration" -n 0 tests/test_services/test_import_module_layout.py`
Expected: FAIL, `ImportError: cannot import name 'import_persistence'`.

- [ ] **Step 3: move the persistence group**

Write the docstring file `$SCRATCH/doc_persistence.txt`:

```
"""Persistance d'un import : des résultats déjà scrapés vers la base (#914, #1186).

Seul point d'entrée : `persist_steps`, et `persist_results` qui l'épuise. Les
rattrapages de lot (datation #972, classification #294, réidentification,
renumérotations #757, #785 et #672) passent avant la première ligne écrite.
Ne clôt jamais la transaction : l'appelant commite ou annule.
"""
```

Run:

```bash
uv run python $SCRATCH/move_symbols.py app/services/import_service.py app/services/import_persistence.py $SCRATCH/doc_persistence.txt \
  Reassignment PassiveSource _identite _CLES_APPARIEMENT _is_empty _merge_fields _resolve_status \
  _NON_FINISHER_STATUSES _NON_FINISHER_FIELDS _non_finisher_overrides _TRANCHE_SIZE _team_key \
  _identity_key _pair_key _source_key _stored_source_key _participation_fields _published_name \
  _proposed_teammates _oriented_teammates _PendingResolution _Persister _redate_heats \
  _reclassify_heats CourseIdentity _reidentify_heats _renumber_relay_split_ranks \
  _renumber_duplicate_ranks _persist_challenges _TWIN_DAYS _drop_course_twin _prepare_batch \
  persist_steps persist_results
```

Expected: `moved 35 symbols from app/services/import_service.py to app/services/import_persistence.py`.

- [ ] **Step 4: rewire the app callers**

`$SCRATCH/rules_a1_app.py`:

```python
RULES = [
    # import_service: the orchestration now calls persistence through its module.
    (r"(?<![\w.])persist_results\(", "import_persistence.persist_results("),
    (r"(?<![\w.])persist_steps\(", "import_persistence.persist_steps("),
    # admin_actions
    (r"import_service\.persist_results\(", "import_persistence.persist_results("),
    (r"import_service\.persist_steps\(", "import_persistence.persist_steps("),
    # batch, bulk_import_service, rescrape_service
    (r"from app\.services\.import_service import (PassiveSource|Reassignment)",
     r"from app.services.import_persistence import \1"),
]
ENSURE = []
```

Run:

```bash
uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a1_app.py app/services/import_service.py app/services/admin_actions.py app/services/batch.py app/services/bulk_import_service.py app/services/rescrape_service.py
```

Then add the import lines by hand (Edit tool):

- `app/services/import_service.py`, the line `from app.services import cache, challenge_service, course_reconciliation, mapping, quality`
  becomes `from app.services import cache, challenge_service, course_reconciliation, import_persistence, mapping, quality`
  (ruff prunes the unused ones in Step 6).
- `app/services/admin_actions.py:51` `from app.services import import_service, opposition_service, sse_relay`
  becomes `from app.services import import_persistence, import_service, opposition_service, sse_relay`.
- `app/services/batch.py:24` now reads `from app.services.import_persistence import PassiveSource, Reassignment`
  (line 23 `from app.services import import_service` stays: batch still calls `import_service.iter_import_event`).

Check the `persist_steps` docstring sentence "Le re-scrape admin les sautait en instanciant `_Persister` lui-même." still reads right; leave it.

- [ ] **Step 5: repoint the tests**

`$SCRATCH/rules_a1_tests.py`:

```python
RULES = [
    (r"import_service\.(persist_results|persist_steps|Reassignment|PassiveSource|mapping)\b",
     r"import_persistence.\1"),
    (r"import_service\.(_is_empty|_merge_fields|_renumber_duplicate_ranks)\b",
     r"import_persistence.\1"),
    (r'setattr\((\s*)import_service,(\s*)"(persist_results|_TRANCHE_SIZE|split_relay_teammates)"',
     r'setattr(\1import_persistence,\2"\3"'),
    (r"from app\.services\.import_service import (PassiveSource|Reassignment)",
     r"from app.services.import_persistence import \1"),
]
ENSURE = [("import_persistence", "import_service")]
```

Run:

```bash
uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a1_tests.py $(/usr/bin/grep -rlE --include='*.py' 'import_service' tests)
```

Hits this must cover (verify each changed with `/usr/bin/grep -rnE 'import_service\.(persist_|Reassignment|PassiveSource|mapping|_is_empty|_merge_fields|_renumber_duplicate_ranks)|setattr\(\s*import_service,\s*"(persist_results|_TRANCHE_SIZE|split_relay_teammates)"' tests`, expected empty):

- `tests/test_services/test_import_service.py:86` (`import_service.mapping`), `:742` and `:743`, `:751` (persist_results patch and restore), `:1106-1117` (`_is_empty`, `_merge_fields`), `:1948`, `:2016`, `:2337`, `:2597` (`_TRANCHE_SIZE`), `:2426`, `:2458` (`split_relay_teammates`)
- `tests/test_services/test_import_homonyms.py:157` (`_TRANCHE_SIZE`)
- `tests/test_services/test_duplicate_rank_renumbering.py:264`
- `tests/test_api/test_scrape_api.py:264` (`Reassignment`)
- `tests/test_services/test_batch.py:715,857,890`, `tests/test_services/test_bulk_import_service.py:253`, `tests/test_cli/test_reports.py:4` (`from ... import PassiveSource|Reassignment`)
- every `import_service.persist_results(` call in `tests/test_chronoplace.py`, `tests/test_chronoweb.py`, `tests/test_oktime.py`, `tests/test_sporthive.py`, `tests/test_services/test_challenge_on_import.py`, `test_concurrent_imports_postgres.py`, `test_merge_absorbed_identity.py`, `test_nameless_identity.py`, `test_opposition_on_import.py`, and any other file the grep in Step 6 still reports.

The multi-line `monkeypatch.setattr(\n    import_service,\n    "..."` form is matched by the `\s*` groups.

- [ ] **Step 6: lint fix-up**

Run:

```bash
uv run ruff check --fix --select F401,I001 app tests
uv run ruff check --select F821,F811 app tests
uv run ruff check .
```

Expected: the F821 pass is clean (a hit means a moved symbol is still referenced from
`import_service`, or a persistence symbol from the dispatch group: fix it by calling
`import_persistence.<public name>` or by making that one name public in its new home).

- [ ] **Step 7: run the layout test and the suite**

Run: `uv run pytest -m "not integration" -n 0 tests/test_services/test_import_module_layout.py`
Expected: PASS.

Run: `uv run pytest -m "not integration"`
Expected: all green (same count as before the task plus 1).

- [ ] **Step 8: commit**

```bash
/usr/bin/git add app/services/import_persistence.py app/services/import_service.py app/services/admin_actions.py app/services/batch.py app/services/bulk_import_service.py app/services/rescrape_service.py tests
/usr/bin/git commit -m "refactor(import): move persistence out of import_service into import_persistence (#1186)"
```

### Task A2: extract `import_dispatch`

**Files:**
- Create: `backend/app/services/import_dispatch.py`
- Modify: `backend/app/services/import_service.py` (keeps only `import_event`, `iter_import_event`, `_confirm_committed`, `_lock_url_and_recheck_cache`), `backend/app/services/admin_actions.py` (two `scrape_all_streaming` calls)
- Modify (repoint): tests listed in Step 5
- Test: `backend/tests/test_services/test_import_module_layout.py`

**Interfaces:**
- Consumes: `import_persistence` from A1.
- Produces: `app.services.import_dispatch` with public `validate_url(url) -> str`,
  `cached_result(db, url, settings) -> dict | None`,
  `scrape_all(url, db, settings, *, single_heat=False, use_cache_probe=True) -> tuple[list[ScrapedResult], FanoutTrace | None]`,
  `scrape_all_streaming(url, db, settings, *, single_heat=False, use_cache_probe=True)` (generator returning `(results, trace)`),
  `fanout_counters(trace) -> dict`, `merge_cached_courses(db, courses, trace) -> list[dict]`,
  and the patch point `registry_scrape_event_all` plus `SessionLocal`. `_make_cache_probe`,
  `_importable`, `_require_event_name` stay private (only used inside the module).

- [ ] **Step 1: add the failing tests** to `tests/test_services/test_import_module_layout.py`

```python
from datetime import date

from app.core.config import Settings
from app.scrapers.base import FanoutTrace, ScrapedResult
from app.services import import_dispatch

URL = "https://chrono.example/epreuve-1186"


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _one_result() -> ScrapedResult:
    return ScrapedResult(
        source_url=URL, provider="klikego", athlete_name="DUPONT", athlete_firstname="Jean",
        bib_number="1", event_name="Triathlon 1186", event_date=date(2026, 5, 16),
        event_type="triathlon-m", total_time="01:59:00",
    )


def test_dispatch_lives_in_import_dispatch():
    for name in (
        "validate_url", "cached_result", "scrape_all", "scrape_all_streaming",
        "fanout_counters", "merge_cached_courses",
    ):
        assert callable(getattr(import_dispatch, name)), name
    for name in (
        "registry_scrape_event_all", "SessionLocal", "registry", "scrape_all_streaming",
        "_scrape_all", "_cached_result", "_validate_url", "_make_cache_probe",
    ):
        assert not hasattr(import_service, name), name


def test_patching_the_dispatch_scraper_reaches_import_event(db_session, monkeypatch):
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return [_one_result()], FanoutTrace(heats_enumerated=1)

    monkeypatch.setattr(import_dispatch, "registry_scrape_event_all", fake)
    outcome = import_service.import_event(db_session, URL, _settings(), force=True)

    assert calls == [URL]
    assert outcome["imported"] == 1


def test_patching_the_dispatch_scraper_reaches_iter_import_event(db_session, monkeypatch):
    calls = []

    def fake(url, **kwargs):
        calls.append(url)
        return [_one_result()], FanoutTrace(heats_enumerated=1)

    monkeypatch.setattr(import_dispatch, "registry_scrape_event_all", fake)
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))

    assert calls == [URL]
    assert phases[-1]["phase"] == "done"
    assert phases[-1]["imported"] == 1
```

Move the module docstring's `from` lines so all imports sit at the top of the file
(ruff I001 sorts them in Step 6).

- [ ] **Step 2: run, expect FAIL**

Run: `uv run pytest -m "not integration" -n 0 tests/test_services/test_import_module_layout.py`
Expected: FAIL, `ImportError: cannot import name 'import_dispatch'`.

- [ ] **Step 3: move the dispatch group and make the crossing names public**

`$SCRATCH/doc_dispatch.txt`:

```
"""Le scrape d'un import : validation d'URL, dispatch vers le fournisseur, cache TTL (#1186).

`registry_scrape_event_all` est le point de substitution des tests : il est lu
ici, par `scrape_all` et `scrape_all_streaming`. Le cache TTL a deux
consommateurs, `cached_result` (court-circuit global par URL) et
`_make_cache_probe` (sonde par heat du fan-out, #156).
"""
```

Run:

```bash
uv run python $SCRATCH/move_symbols.py app/services/import_service.py app/services/import_dispatch.py $SCRATCH/doc_dispatch.txt \
  _validate_url _merge_cached_courses _fanout_counters _make_cache_probe _scrape_all \
  scrape_all_streaming _importable _require_event_name _cached_result
```

Expected: `moved 9 symbols ...`.

`$SCRATCH/rules_a2_dispatch.py` (renames inside the new module, docstrings included):

```python
RULES = [
    (r"(?<![\w.])_validate_url\b", "validate_url"),
    (r"(?<![\w.])_merge_cached_courses\b", "merge_cached_courses"),
    (r"(?<![\w.])_fanout_counters\b", "fanout_counters"),
    (r"(?<![\w.])_scrape_all\b", "scrape_all"),
    (r"(?<![\w.])_cached_result\b", "cached_result"),
]
ENSURE = []
```

`$SCRATCH/rules_a2_service.py` (the orchestration calls through the module):

```python
RULES = [
    (r"(?<![\w.`])_validate_url\(", "import_dispatch.validate_url("),
    (r"(?<![\w.`])_merge_cached_courses\(", "import_dispatch.merge_cached_courses("),
    (r"(?<![\w.`])_fanout_counters\(", "import_dispatch.fanout_counters("),
    (r"(?<![\w.`])_scrape_all\(", "import_dispatch.scrape_all("),
    (r"(?<![\w.`])_cached_result\(", "import_dispatch.cached_result("),
    (r"(?<![\w.`])scrape_all_streaming\(", "import_dispatch.scrape_all_streaming("),
    # docstring mentions
    (r"`_cached_result`", "`import_dispatch.cached_result`"),
    (r"`_scrape_all`", "`import_dispatch.scrape_all`"),
]
ENSURE = []
```

`$SCRATCH/rules_a2_admin.py`:

```python
RULES = [(r"import_service\.scrape_all_streaming\(", "import_dispatch.scrape_all_streaming(")]
ENSURE = []
```

Run:

```bash
uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a2_dispatch.py app/services/import_dispatch.py
uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a2_service.py app/services/import_service.py
uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a2_admin.py app/services/admin_actions.py
```

Edit imports by hand:

- `app/services/import_service.py`: the `from app.services import ...` line gains `import_dispatch`
  (`from app.services import cache, challenge_service, course_reconciliation, import_dispatch, import_persistence, mapping, quality`;
  Step 6 prunes it to `from app.services import import_dispatch, import_persistence`).
- `app/services/admin_actions.py`: `from app.services import import_dispatch, import_persistence, import_service, opposition_service, sse_relay`.

Replace the module docstring of `app/services/import_service.py` with:

```python
"""Orchestration de l'import d'une épreuve entière (#1186).

`import_event` (bloquant) et `iter_import_event` (générateur SSE) enchaînent le
cache TTL et le scrape (`import_dispatch`), le verrou d'URL (#1024), puis la
persistance (`import_persistence`) dans une transaction qu'ils commitent ou
annulent, avec reprise sur deadlock.
"""
```

- [ ] **Step 4: verify nothing private crosses**

Run: `uv run pytest -m "not integration" -n 0 tests/test_service_boundaries.py`
Expected: PASS (all crossings go through public names).

- [ ] **Step 5: repoint the tests**

`$SCRATCH/rules_a2_tests.py`:

```python
RULES = [
    (r'setattr\((\s*)import_service,(\s*)"(registry_scrape_event_all|SessionLocal)"',
     r'setattr(\1import_dispatch,\2"\3"'),
    (r"import_service\.(registry_scrape_event_all|registry|scrape_all_streaming)\b",
     r"import_dispatch.\1"),
    (r"import_service\._scrape_all\b", "import_dispatch.scrape_all"),
    (r"import_service\._make_cache_probe\b", "import_dispatch._make_cache_probe"),
    (r"from app\.services\.import_service import _validate_url",
     "from app.services.import_dispatch import validate_url"),
    (r"(?<![\w.])_validate_url\(", "validate_url("),
]
ENSURE = [("import_dispatch", "import_service")]
```

Run:

```bash
uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a2_tests.py $(/usr/bin/grep -rlE --include='*.py' 'import_service' tests)
```

Hits this must cover:

- `tests/test_services/conftest.py:107-108` (`patch_scraper`, multi-line)
- `tests/test_api/test_rate_limit.py:31-32` (multi-line; the `:115` patch of `iter_import_event` stays on `import_service`)
- `tests/test_api/test_other_api.py:90-91`
- `tests/test_api/test_scrape_api.py:230-231`, `:449-450`, `:488`
- `tests/test_services/test_admin_actions.py:696`, `:825`, `:1205`, `:2511`, `:2575`
- `tests/test_services/test_rescrape_service.py:204`, `:226`, `:253`, `:285`
- `tests/test_services/test_import_service.py:666`, `:680-681`, `:686`, `:690`, `:692`, `:709`, `:719-720`, `:729`, `:808`, `:816`, `:1502`, `:1522`, `:1530` (and the `_validate_url(` calls below them), `:1552`, `:1560`, `:1562`, `:1584`, `:1600` (`SessionLocal`), `:1608`, `:1610`, `:1632`, `:1633`, `:1762`, `:1799`, `:1829`, `:1861`, `:1863`, `:1893`, `:1895`, `:1914`, `:2768`, `:2775`, `:2796`
- `tests/test_registry.py:957` (`import_service._scrape_all`) and any `import_service.registry` in it
- any other `registry_scrape_event_all` patch the check below reports

Check:

```bash
/usr/bin/grep -rnE --include='*.py' 'import_service\.(registry|registry_scrape_event_all|SessionLocal|scrape_all_streaming|_scrape_all|_make_cache_probe|_validate_url|_cached_result)|setattr\(\s*import_service,\s*"(registry_scrape_event_all|SessionLocal)"' tests app
```

Expected: no output. `import_service.course_repository` (`test_import_service.py:1410`) stays: `_confirm_committed` lives in `import_service` and still imports `course_repository`.

- [ ] **Step 6: lint fix-up**

```bash
uv run ruff check --fix --select F401,I001 app tests
uv run ruff check --select F821,F811 app tests
uv run ruff check .
```

Expected: clean. `import_service.py` imports end up close to: `logging`, `Iterator`, `datetime`,
`Session`, `Settings`, `InvalidUrlError`, `ProviderNotSupportedError`, `ScraperError`, `utcnow`,
`course_repository`, `lock_repository`, `import_dispatch`, `import_persistence`, `deadlock_retries`.

- [ ] **Step 7: run**

Run: `uv run pytest -m "not integration" -n 0 tests/test_services/test_import_module_layout.py`
Expected: PASS (4 tests).

Run: `uv run pytest -m "not integration"`
Expected: all green.

- [ ] **Step 8: commit**

```bash
/usr/bin/git add app/services/import_dispatch.py app/services/import_service.py app/services/admin_actions.py tests
/usr/bin/git commit -m "refactor(import): move scrape dispatch and TTL cache into import_dispatch (#1186)"
```

### Task A3: move the admin rescrape and source switch to `course_rescrape_service`

**Files:**
- Create: `backend/app/services/course_rescrape_service.py`
- Modify: `backend/app/services/admin_actions.py` (lose the nine symbols; `_course_or_404`, `_instantane`, `_CHAMPS_COURSE` become public)
- Modify: `backend/app/api/v1/admin_course_rescrape.py:8,24,45`, `backend/app/api/v1/admin_course_sources.py:27,79,109`
- Modify (repoint): `tests/test_api/test_admin_course_rescrape.py`, `tests/test_api/test_course_source_switch_api.py`, `tests/test_services/test_admin_actions.py`, `tests/test_repositories/test_course_source.py:119` (docstring)
- Test: `backend/tests/test_services/test_import_module_layout.py`

**Interfaces:**
- Consumes: `import_dispatch.scrape_all_streaming`, `import_persistence.persist_results`, `import_persistence.persist_steps`.
- Produces: `app.services.course_rescrape_service` with
  `iter_rescrape_course(db, *, course_id, user_id, settings) -> Iterator[dict]`,
  `iter_switch_course_source(db, *, course_id, source_id, user_id, settings) -> Iterator[dict]`,
  `delete_course_source(db, *, course_id, source_id, user_id) -> None` (same signatures as today);
  `admin_actions.course_or_404(db, course_id) -> Course`,
  `admin_actions.instantane(entite, champs) -> dict`, `admin_actions.CHAMPS_COURSE`.

- [ ] **Step 1: add the failing test** to `tests/test_services/test_import_module_layout.py`

```python
def test_admin_rescrape_lives_in_course_rescrape_service():
    from app.services import admin_actions, course_rescrape_service

    for name in ("iter_rescrape_course", "iter_switch_course_source", "delete_course_source"):
        assert callable(getattr(course_rescrape_service, name)), name
        assert not hasattr(admin_actions, name), name
    assert callable(admin_actions.course_or_404)
    assert callable(admin_actions.instantane)
    assert admin_actions.CHAMPS_COURSE == ("name", "event_date", "event_type", "is_relay")
```

- [ ] **Step 2: run, expect FAIL**

Run: `uv run pytest -m "not integration" -n 0 tests/test_services/test_import_module_layout.py::test_admin_rescrape_lives_in_course_rescrape_service`
Expected: FAIL, `ImportError: cannot import name 'course_rescrape_service'`.

- [ ] **Step 3: make the shared helpers public in `admin_actions`**

`$SCRATCH/rules_a3_helpers.py`:

```python
RULES = [
    (r"(?<![\w.])_course_or_404\b", "course_or_404"),
    (r"(?<![\w.])_instantane\b", "instantane"),
    (r"(?<![\w.])_CHAMPS_COURSE\b", "CHAMPS_COURSE"),
]
ENSURE = []
```

Run: `uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a3_helpers.py app/services/admin_actions.py`

- [ ] **Step 4: move the nine symbols**

`$SCRATCH/doc_rescrape.txt`:

```
"""Re-scrape d'une épreuve et bascule de sa source, depuis le back-office (#118, #285, #1186).

Deux gestes SSE qui réécrivent une épreuve depuis sa source : la garde (404,
409 par `course_locks`) est synchrone, puis un thread de travail
(`sse_relay.relay`) scrape par `import_dispatch` et persiste par
`import_persistence`. La suppression d'une source inactive (#739) vit ici avec
eux. Le verrou d'épreuve est en base (`lock_courses_or_409`).
"""
```

Run:

```bash
uv run python $SCRATCH/move_symbols.py app/services/admin_actions.py app/services/course_rescrape_service.py $SCRATCH/doc_rescrape.txt \
  _source_dicts iter_switch_course_source delete_course_source _stream_switch_course_source \
  _require_course_unchanged _require_same_event iter_rescrape_course _stream_rescrape _drain_scrape
```

Expected: `moved 9 symbols ...`.

`$SCRATCH/rules_a3_moved.py`:

```python
RULES = [
    (r"(?<![\w.`])course_or_404\(", "admin_actions.course_or_404("),
    (r"(?<![\w.`])instantane\(", "admin_actions.instantane("),
    (r"(?<![\w.`])CHAMPS_COURSE\b", "admin_actions.CHAMPS_COURSE"),
    (r"`CHAMPS_COURSE`", "`admin_actions.CHAMPS_COURSE`"),
]
ENSURE = [("admin_actions", "sse_relay")]
```

Run: `uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a3_moved.py app/services/course_rescrape_service.py`

(`ENSURE` anchors on the copied `from app.services import import_dispatch, import_persistence, import_service, opposition_service, sse_relay` line.)

- [ ] **Step 5: repoint the routers and the tests**

`$SCRATCH/rules_a3_callers.py`:

```python
RULES = [
    (r"admin_actions\.(iter_rescrape_course|iter_switch_course_source|delete_course_source)\b",
     r"course_rescrape_service.\1"),
    (r'setattr\((\s*)admin_actions,(\s*)"(iter_rescrape_course|iter_switch_course_source)"',
     r'setattr(\1course_rescrape_service,\2"\3"'),
]
ENSURE = [("course_rescrape_service", "admin_actions")]
```

Run:

```bash
uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a3_callers.py app/api/v1/admin_course_rescrape.py app/api/v1/admin_course_sources.py tests/test_api/test_admin_course_rescrape.py tests/test_api/test_course_source_switch_api.py tests/test_services/test_admin_actions.py tests/test_repositories/test_course_source.py
```

Hits this covers: `admin_course_rescrape.py:8` (docstring) and `:45`; `admin_course_sources.py:79`, `:109`;
`test_admin_course_rescrape.py:11`, `:92`, `:129`, `:146`, `:152`, `:164`, `:175`;
`test_course_source_switch_api.py:10-11`, `:137-138`, `:184-185`, `:206`, `:212-213`, `:228-229`, `:245-246`;
`test_admin_actions.py:757` to `:1347` and `:2415`, `:2513`, `:2543`, `:2577`, `:2594`;
`test_course_source.py:119` (docstring).

Then replace the persister guard at `tests/test_services/test_admin_actions.py:2427-2431` with:

```python
def test_no_caller_instantiates_the_persister_outside_import_persistence():
    """#914 : un seul point d'entrée public porte rattrapages de lot et boucle."""
    import inspect

    from app.services import course_rescrape_service

    assert "_Persister(" not in inspect.getsource(admin_actions)
    assert "_Persister(" not in inspect.getsource(course_rescrape_service)
```

- [ ] **Step 6: lint fix-up**

```bash
uv run ruff check --fix --select F401,I001 app tests
uv run ruff check --select F821,F811 app tests
uv run ruff check .
```

Expected: clean. `admin_actions` no longer imports `import_dispatch`, `import_persistence`,
`import_service`, `sse_relay` or `deadlock_retries` if nothing left uses them (ruff decides).

- [ ] **Step 7: run**

Run: `uv run pytest -m "not integration" -n 0 tests/test_services/test_import_module_layout.py tests/test_service_boundaries.py`
Expected: PASS.

Run: `uv run pytest -m "not integration"`
Expected: all green.

- [ ] **Step 8: commit**

```bash
/usr/bin/git add app/services/course_rescrape_service.py app/services/admin_actions.py app/api/v1/admin_course_rescrape.py app/api/v1/admin_course_sources.py tests
/usr/bin/git commit -m "refactor(admin): move course rescrape and source switch into course_rescrape_service (#1186)"
```

### Task A4: stale references and module inventory

**Files:**
- Modify: `backend/AGENTS.md:32-46` (services inventory), `:64-70` (Cache TTL paragraph)
- Modify (docstrings and comments only): `backend/app/core/exceptions.py:54`, `backend/app/repositories/course_repository.py:214`, `backend/app/schemas/scrape.py:19`, `backend/app/scrapers/oktime.py:689`, `backend/app/scrapers/raceresult.py:1630`, `backend/app/scrapers/registry.py:112`, `backend/app/scrapers/runnerbreizh.py:431`, `backend/app/scrapers/sporthive.py:225,601`, `backend/app/services/batch.py:156`, `backend/app/services/quality.py:22`, `backend/app/scrapers/AGENTS.md:108`, `docs/api/*.md` hits

**Interfaces:** none (docs only).

- [ ] **Step 1: list the stale mentions**

```bash
/usr/bin/grep -rnE "import_service\._|admin_actions\.(iter_rescrape_course|iter_switch_course_source|delete_course_source|_course_or_404|_instantane)" app docs/api ../docs/api AGENTS.md app/scrapers/AGENTS.md 2>/dev/null
```

- [ ] **Step 2: rewrite each mention to the new home**

`$SCRATCH/rules_a4_docs.py`:

```python
RULES = [
    (r"import_service\._(validate_url|scrape_all|cached_result|fanout_counters|merge_cached_courses)\b",
     r"import_dispatch.\1"),
    (r"import_service\.(_make_cache_probe|_require_event_name|_importable)\b", r"import_dispatch.\1"),
    (r"import_service\.(_Persister|_redate_heats|_reclassify_heats|_reidentify_heats|_renumber_duplicate_ranks|_renumber_relay_split_ranks|_prepare_batch)\b",
     r"import_persistence.\1"),
    (r"admin_actions\.(iter_rescrape_course|iter_switch_course_source|delete_course_source)\b",
     r"course_rescrape_service.\1"),
]
ENSURE = []
```

Run (from `backend/`):

```bash
uv run python $SCRATCH/rewrite.py $SCRATCH/rules_a4_docs.py $(/usr/bin/grep -rlE "import_service\._|admin_actions\.(iter_rescrape_course|iter_switch_course_source|delete_course_source)" app ../docs/api app/scrapers/AGENTS.md)
```

`app/scrapers/t2area.py:213` cites `import_service._match_without_bib`, which no longer exists anywhere:
rewrite that phrase by hand to `l'appariement par athlète de la persistance (import_persistence)`.

- [ ] **Step 3: update `backend/AGENTS.md`**

In the `app/services/` bullet (lines 32-46), replace
`` Modules : `mapping`, `cache` (TTL), `scrape_service`,
  `import_service`, `stats_service`, `geocode_service`, `` with:

```
  ce qui sert ailleurs devient public. Modules : `mapping`, `cache` (TTL), `scrape_service`,
  l'import en trois modules (#1186) : `import_service` (orchestration, transaction,
  verrou d'URL), `import_dispatch` (validation d'URL, dispatch vers le fournisseur,
  cache TTL ; `registry_scrape_event_all`, le point de substitution des tests, y est
  lu) et `import_persistence` (`persist_steps`, seul point d'entrée de l'écriture,
  et les passes de lot), `course_rescrape_service` (re-scrape admin et bascule de
  source, #118, #285), `stats_service`, `geocode_service`,
```

Replace the Cache TTL sentence `Deux consommateurs, tous deux dans `import_service` : `_cached_result`, le court-circuit global par URL (sauté par `force=True`), et `_make_cache_probe`, la sonde par heat du fan-out Klikego (#156).` with:

```
Deux consommateurs, tous deux dans `import_dispatch` : `cached_result`, le
court-circuit global par URL (sauté par `force=True`), et `_make_cache_probe`, la
sonde par heat du fan-out Klikego (#156).
```

- [ ] **Step 4: verify**

```bash
/usr/bin/grep -rnE "import_service\._|admin_actions\.(iter_rescrape_course|iter_switch_course_source|delete_course_source)" app ../docs/api AGENTS.md
uv run ruff check .
uv run pytest -m "not integration"
```

Expected: grep empty, ruff clean, suite green.

- [ ] **Step 5: commit**

```bash
/usr/bin/git add AGENTS.md app ../docs/api
/usr/bin/git commit -m "docs(backend): point module inventory and docstrings at the split import modules (#1186)"
```


# Partie B

## Partie B : #1193, #1191, #1212

Rappels valables pour toutes les tâches B :

- Commandes backend depuis `backend/`, frontend depuis `frontend/`.
- git en commandes simples et séparées (`/usr/bin/git add …` puis `/usr/bin/git commit -m …`), Conventional Commits en anglais, **aucun trailer `Co-Authored-By`**.
- Copie visible en français, identifiants et noms de tests en anglais (les fichiers de tests existants mêlent les deux : suivre le fichier touché).
- Jamais de tiret (—, –, -) pour ponctuer une phrase dans la prose, les commentaires ou la copie UI.

---

### Task B1: Sportinnovation, date de course contredite par l'année de l'événement (#1193)

Mesure (prod, 06/10) : épreuve 1047, `https://sportinnovation.fr/Evenements/Resultats/6450`. La page détail `/Evenements/Resultats/Detail/6450/1` porte `<h6 class="col-12 text-center pb-2 pt-2 bg-light">Triathlon L (10/10/2026)</h6>` et le lien de partage `…&t=Résultats - Triathlon L - Bayman - Triathlon du Mont Saint-Michel 2024`. Vérifié : `_parse_race_meta` rend `('Triathlon L', 'Bayman - Triathlon du Mont Saint-Michel 2024', date(2026, 10, 10))`. La course sœur M (`Detail/6433/1`) publie `06/10/2024`. Le scraper recopie l'erreur de la source.

**Files:**
- Modify: `backend/app/scrapers/sportinnovation.py` (nouveau `_TITLE_YEAR_RE`, nouvelle fonction `_reconcile_race_dates`, boucle legacy de `scrape_event_all` l. 695-714)
- Modify: `backend/app/scrapers/AGENTS.md` (ligne « TimePulse, Sportinnovation » du tableau des fournisseurs)
- Test: `backend/tests/test_sportinnovation.py`

**Interfaces:**
- Consumes: `_fetch_race_meta(race_id, client) -> tuple[str, date | None]`, `_fetch_all_pages(event_id, client) -> tuple[str, list[list[str]], dict[str, int]]`, `_parse_html_row(tds, col, race_url, race_name, course_name, event_date)` (existants).
- Produces: `_reconcile_race_dates(metas: list[tuple[str, date | None]]) -> list[date | None]` (privé au module ; une date par course, même ordre que `metas`).

- [ ] **Step 1: Write the failing tests**

Ajouter après les tests `_compose_course_name` (section des helpers), puis après `test_legacy_event_without_race_select_falls_back_on_the_event_id` pour le test de bout en bout :

```python
# ── _reconcile_race_dates : date de course contredite par l'année du titre (#1193)
#
# Mesure prod 06/10 : la course L de « Bayman - Triathlon du Mont Saint-Michel
# 2024 » publie « (10/10/2026) » sur sa page détail, sa sœur M « (06/10/2024) ».

BAYMAN = "Bayman - Triathlon du Mont Saint-Michel 2024"


def test_reconcile_race_dates_replaces_a_date_contradicting_the_title_year():
    dates = _si._reconcile_race_dates([
        (BAYMAN, date(2024, 10, 6)),
        (BAYMAN, date(2026, 10, 10)),
        (BAYMAN, date(2024, 10, 6)),
    ])
    assert dates == [date(2024, 10, 6), date(2024, 10, 6), date(2024, 10, 6)]


def test_reconcile_race_dates_takes_the_most_frequent_sibling_date():
    dates = _si._reconcile_race_dates([
        (BAYMAN, date(2024, 10, 5)),
        (BAYMAN, date(2024, 10, 6)),
        (BAYMAN, date(2024, 10, 6)),
        (BAYMAN, date(2026, 10, 10)),
    ])
    assert dates[3] == date(2024, 10, 6)


def test_reconcile_race_dates_breaks_a_frequency_tie_on_the_earliest_date():
    dates = _si._reconcile_race_dates([
        (BAYMAN, date(2024, 10, 6)),
        (BAYMAN, date(2024, 10, 5)),
        (BAYMAN, date(2026, 10, 10)),
    ])
    assert dates[2] == date(2024, 10, 5)


def test_reconcile_race_dates_drops_the_date_without_a_matching_sibling():
    assert _si._reconcile_race_dates([(BAYMAN, date(2026, 10, 10))]) == [None]


def test_reconcile_race_dates_keeps_dates_that_agree_with_the_title():
    """Carnac : les aquathlons courent la veille des triathlons, même année."""
    carnac = "Triathlon de Carnac 2025"
    metas = [(carnac, date(2025, 10, 4)), (carnac, date(2025, 10, 5))]
    assert _si._reconcile_race_dates(metas) == [date(2025, 10, 4), date(2025, 10, 5)]


def test_reconcile_race_dates_leaves_a_title_without_year_alone():
    metas = [("BayMan", date(2026, 6, 1)), ("BayMan", None)]
    assert _si._reconcile_race_dates(metas) == [date(2026, 6, 1), None]


def test_reconcile_race_dates_ignores_a_title_carrying_two_years():
    """« Saison 2024-2025 » ne désigne pas une année : rien n'est corrigé."""
    metas = [("Challenge 2024-2025", date(2025, 3, 1))]
    assert _si._reconcile_race_dates(metas) == [date(2025, 3, 1)]
```

```python
def test_legacy_event_rewrites_a_race_date_contradicting_the_event_year(monkeypatch):
    html = (
        '<select name="raceSearch">'
        '<option value="6450">L</option><option value="6433">M</option></select>'
    )
    _legacy(monkeypatch, html, {"6450": [["a", "1"]], "6433": [["b", "2"]]})
    metas = {
        "6450": (BAYMAN, date(2026, 10, 10)),
        "6433": (BAYMAN, date(2024, 10, 6)),
    }
    monkeypatch.setattr(_si, "_fetch_race_meta", lambda rid, c: metas[rid])
    monkeypatch.setattr(
        _si, "_parse_html_row",
        lambda tds, col, race_url, race_name, course_name, event_date: (race_url, event_date),
    )

    resultats = _si.scrape_event_all("https://sportinnovation.fr/Evenements/Resultats/6450")

    base = "https://sportinnovation.fr/Evenements/Resultats"
    assert resultats == [
        (f"{base}/6450", date(2024, 10, 6)),
        (f"{base}/6433", date(2024, 10, 6)),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sportinnovation.py -k "reconcile_race_dates or contradicting_the_event_year" -n 0 -v`
Expected: FAIL, `AttributeError: module 'app.scrapers.sportinnovation' has no attribute '_reconcile_race_dates'` pour les tests unitaires, et `(…/6450, date(2026, 10, 10))` au lieu de 2024 pour le test de bout en bout.

- [ ] **Step 3: Write the implementation**

Ajouter `from collections import Counter` aux imports, puis sous `_compose_course_name` :

```python
_TITLE_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")


def _reconcile_race_dates(metas: list[tuple[str, date | None]]) -> list[date | None]:
    """Écarte la date d'une course que l'année du titre d'événement contredit (#1193).

    Chaque page détail porte sa propre date, et la source en publie de fausses :
    la course L de « … Mont Saint-Michel 2024 » est datée du 10/10/2026, sa sœur
    M du 06/10/2024. Quand le titre porte une seule année, une date d'une autre
    année prend la date la plus fréquente des courses sœurs qui concordent (la
    plus ancienne à égalité), sinon `None`. Un titre sans année, ou à deux
    années (« 2024-2025 »), ne corrige rien.
    """
    def title_year(event_name: str) -> int | None:
        years = {int(y) for y in _TITLE_YEAR_RE.findall(event_name)}
        return years.pop() if len(years) == 1 else None

    agreeing = Counter(
        d for name, d in metas if d is not None and d.year == title_year(name)
    )
    reconciled: list[date | None] = []
    for name, d in metas:
        year = title_year(name)
        if d is None or year is None or d.year == year:
            reconciled.append(d)
            continue
        fallback = min(agreeing, key=lambda c: (-agreeing[c], c)) if agreeing else None
        logger.warning(
            "Date %s contredite par l'année %s du titre « %s » : remplacée par %s",
            d, year, name, fallback,
        )
        reconciled.append(fallback)
    return reconciled
```

Remplacer la boucle legacy de `scrape_event_all` (l. 695-714) par une collecte en deux temps :

```python
        races = []
        for rid in race_ids:
            race_name, rows, col = _fetch_all_pages(rid, client)
            event_name, event_date = _fetch_race_meta(rid, client)
            races.append((rid, race_name, rows, col, event_name, event_date))
        dates = _reconcile_race_dates([(r[4], r[5]) for r in races])

        all_results: list[ScrapedResult] = []
        seen_bibs: set[tuple[str, str]] = set()

        for (rid, race_name, rows, col, event_name, _), event_date in zip(races, dates):
            course_name = _compose_course_name(event_name, race_name)
            race_url = f"https://sportinnovation.fr/Evenements/Resultats/{rid}"
            for tds in rows:
                bib_idx = col.get("bib", 1)
                bib_val = tds[bib_idx].strip() if bib_idx < len(tds) else ""
                key = (rid, bib_val)
                if key in seen_bibs:
                    continue
                seen_bibs.add(key)
                all_results.append(
                    _parse_html_row(tds, col, race_url, race_name, course_name, event_date)
                )

        return all_results
```

Note pour l'exécutant : l'ensemble `agreeing` mêle les courses de titres différents seulement si la page agrège plusieurs événements. Ce n'est pas le cas mesuré (un `<select name=raceSearch>` par événement), donc pas de regroupement par titre.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_sportinnovation.py -n 0 -v`
Expected: PASS (tous, y compris `test_legacy_event_discovers_every_race_and_dedupes_bibs_per_race`, dont le titre « BayMan » n'a pas d'année).

- [ ] **Step 5: Document the rule**

Dans `backend/app/scrapers/AGENTS.md`, ligne « TimePulse, Sportinnovation » du tableau, ajouter à la fin de la cellule « En bref » :

```
Sportinnovation date chaque course sur sa page détail, et la source en publie de fausses (épreuve 6450 : « (10/10/2026) » dans un événement « … 2024 », #1193) : une date d'une autre année que celle du titre prend celle des courses sœurs (`_reconcile_race_dates`), sinon aucune.
```

- [ ] **Step 6: Lint and commit**

Run: `uv run ruff check app/scrapers/sportinnovation.py tests/test_sportinnovation.py`
Expected: `All checks passed!`

```bash
/usr/bin/git add backend/app/scrapers/sportinnovation.py backend/app/scrapers/AGENTS.md backend/tests/test_sportinnovation.py
```
```bash
/usr/bin/git commit -m "fix(sportinnovation): drop a race date contradicting the event title year (#1193)"
```

Suite hors branche (session prod) : rescraper l'épreuve 1047 après déploiement.

---

### Task B2: Reproduire le #418 de la fiche épreuve en `next dev` (#1191), point de décision

Tâche d'enquête : pas de code applicatif, pas de commit. Elle décide si B3 s'applique telle quelle ou si une autre cause se corrige à sa place.

**Files:** aucun dans le dépôt. Notes dans le scratchpad de session.

- [ ] **Step 1: Préparer un backend local avec une épreuve et une session admin**

```bash
cd backend && uv run python scripts/reset_db.py --yes
```
(seed démo inclus.) Lancer le backend en arrière-plan : `uv run python scripts/dev_server.py`.

Créer un superutilisateur et une session, et afficher le jeton et le nom du cookie :

```bash
uv run python -m app.cli grant-role --help
```
puis, selon la procédure d'amorçage de `backend/app/cli/AGENTS.md` (« `grant-role` », l'utilisateur doit exister) :

```bash
uv run python -c "
from app.core.database import SessionLocal
from app.repositories import user_repository
db = SessionLocal(); user_repository.create(db, email='repro@exemple.fr'); db.commit()"
```
```bash
uv run python -m app.cli grant-role --email repro@exemple.fr --role admin
```
```bash
uv run python -c "
from app.core.database import SessionLocal
from app.core.config import get_settings
from app.api.v1.auth import session_cookie_name
from app.repositories import user_repository
from app.services.auth import session as session_service
db = SessionLocal()
u = user_repository.find_by_email(db, 'repro@exemple.fr')[0]
print(session_cookie_name(get_settings()), session_service.open_for(db, u)); db.commit()"
```

En local, `AUTH_COOKIE_SECURE=false` évite le préfixe `__Host-` qui exige HTTPS (même motif que la fixture `session_de_saisie` de `tests/test_api/conftest.py`). Si le site exige un code d'accès en local, le poser avec `uv run python -m app.cli set-site-code --help`.

- [ ] **Step 2: Lancer le front en dev**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Reproduire**

Dans Chromium (Claude in Chrome ou Playwright), poser le cookie de session (et celui d'accès au site) sur l'origine du front, puis ouvrir dans cet ordre, console ouverte :
1. `/courses/<id>` en accès direct (3 rechargements) ;
2. `/athletes/<id>` puis `/courses/<id>` par navigation ;
3. même parcours sans session.

Relever chaque message `Hydration failed` / `Text content does not match` : en dev, React donne le diff serveur/client et le composant fautif.

- [ ] **Step 4: Décider**

- Écart dans `AppNav` ou `UserMenu` (bloc compte du rail ou topbar) : appliquer B3 telle quelle, la PR pourra dire `Closes #1191`.
- Écart ailleurs : remplacer B3 par une tâche équivalente sur le composant trouvé (test d'hydratation `renderToString` puis `hydrateRoot` sur le même modèle, correctif, commit `fix(frontend): … (#1191)`), et le consigner pour la PR.
- Aucun écart reproduit : appliquer B3 (suspect n°1, même patron que #1090) ; la PR dira `Refs #1191` et l'issue reste ouverte jusqu'à la recette prod.

Arrêter les deux serveurs à la fin.

---

### Task B3: Lire la session hydratée dans `AppNav` et `UserMenu` (#1191)

`useHydratedSession` (#1090) masque `data` avant l'hydratation, mais garde `isPending: false` et `errorUpdateCount` du cache : `UserMenu` rendrait alors « Se connecter » au premier passage client là où le serveur rend `SessionEnLecture` (`isPending` vrai, pas de données), et `AppNav` pourrait rendre la branche « Session indisponible » si une erreur est déjà en cache. Le hook doit rendre, avant l'hydratation, exactement l'état du serveur : en lecture, sans données, sans échec, sans requête en cours.

**Files:**
- Modify: `frontend/lib/queries/auth.ts:105-115` (`useHydratedSession`)
- Modify: `frontend/components/layout/AppNav.tsx:10,43`
- Modify: `frontend/components/auth/UserMenu.tsx:12,39`
- Test: `frontend/lib/queries/hydrated-session.test.tsx`
- Test: `frontend/components/auth/UserMenu.hydration.test.tsx` (nouveau)

**Interfaces:**
- Consumes: `useSession()`, `useHydrated()` (`lib/queries/auth.ts`), `queryKeys.session()` (`lib/queries/keys.ts`).
- Produces: `useHydratedSession()` rend, avant hydratation, `{ ...session, data: undefined, isPending: true, errorUpdateCount: 0, isFetching: false }` ; inchangé ensuite.

- [ ] **Step 1: Write the failing tests**

Nouveau fichier `frontend/components/auth/UserMenu.hydration.test.tsx` :

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/lib/queries/keys";
import type { SessionUser } from "@/lib/types";

const { getSession, logout, captureEvent } = vi.hoisted(() => ({
  // Jamais résolue : le serveur n'a pas la session, le client la lit dans son cache.
  getSession: vi.fn(() => new Promise(() => {})),
  logout: vi.fn(),
  captureEvent: vi.fn(),
}));

vi.mock("@/lib/posthog", () => ({ captureEvent }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/courses/1",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, logout } };
});

import { UserMenu } from "./UserMenu";

const SESSION: SessionUser = {
  id: 1,
  email: "admin@exemple.fr",
  display_name: "Admin",
  created_at: "2026-08-01T14:54:28Z",
  permissions: ["athletes:write"],
  roles: [],
  groups: [],
  can_administer: true,
};

function arbre(client: QueryClient) {
  return (
    <QueryClientProvider client={client}>
      <UserMenu />
    </QueryClientProvider>
  );
}

describe("UserMenu hydration (#1191)", () => {
  it("hydrates without mismatch when the session is already cached, then shows the account", async () => {
    const html = renderToString(arbre(new QueryClient()));

    const conteneur = document.createElement("div");
    conteneur.innerHTML = html;
    document.body.appendChild(conteneur);
    const ecart = vi.fn();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    client.setQueryData(queryKeys.session(), SESSION);

    await act(async () => {
      hydrateRoot(conteneur, arbre(client), { onRecoverableError: ecart });
    });

    expect(ecart).not.toHaveBeenCalled();
    expect(conteneur.querySelector('[aria-label="Compte — admin@exemple.fr"]')).not.toBeNull();
  });
});
```

Avant d'écrire l'assertion finale, vérifier l'`aria-label` exact du bouton de compte dans `UserMenu.tsx:137` (`Compte — ${session.email}`) et le reprendre tel quel.

Dans `frontend/lib/queries/hydrated-session.test.tsx`, ajouter au `describe` existant :

```tsx
  it("renders the server's pending state before hydration, even with a cached error", async () => {
    function Etat() {
      const s = useHydratedSession();
      return <p>{`${s.isPending}|${s.errorUpdateCount}|${s.isFetching}|${s.data === undefined}`}</p>;
    }
    const html = renderToString(
      <QueryClientProvider client={new QueryClient()}>
        <Etat />
      </QueryClientProvider>,
    );
    expect(html).toContain("true|0|false|true");
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test -- components/auth/UserMenu.hydration.test.tsx lib/queries/hydrated-session.test.tsx`
Expected: FAIL. `UserMenu.hydration` : `ecart` appelé (le client rend le menu de compte, le serveur `SessionEnLecture`). `hydrated-session` : le second test passe peut‑être déjà au serveur ; s'il passe, le garder comme garde de non‑régression (le premier échec suffit à justifier le correctif).

- [ ] **Step 3: Write the implementation**

`frontend/lib/queries/auth.ts`, remplacer le corps de `useHydratedSession` et compléter sa docstring :

```ts
/**
 * `useSession`, sans session tant que le composant n'est pas hydraté (#1090).
 *
 * Le serveur n'a jamais la session. React Query rend pourtant le cache dès le
 * premier rendu client : quand `/auth/me` a répondu avant l'arrivée d'une page
 * streamée (fiche athlète, fiche épreuve), ce rendu différait du HTML serveur,
 * d'où l'erreur d'hydratation #418 et un second rendu complet de la frontière.
 * Avant l'hydratation, le hook rend donc l'état exact du serveur : en lecture,
 * sans données, sans échec, sans requête en cours (#1191, la topbar lisait
 * `isPending` et `errorUpdateCount`). Tout composant d'un écran rendu côté
 * serveur lit la session par ici.
 */
export function useHydratedSession() {
  const session = useSession();
  const hydrate = useHydrated();
  if (hydrate) return session;
  return {
    ...session,
    data: undefined,
    isPending: true,
    errorUpdateCount: 0,
    isFetching: false,
  } as typeof session;
}
```

`frontend/components/layout/AppNav.tsx` : import `useHydratedSession` à la place de `useSession` (l. 10), et l. 43 :

```ts
  const { data: session, errorUpdateCount: echecsSession, isFetching: sessionEnCours, refetch: relireSession } = useHydratedSession();
```

`frontend/components/auth/UserMenu.tsx` : `import { useHydratedSession, useLogout } from "@/lib/queries/auth";` (l. 12) et l. 39 :

```ts
  const { data: session, isPending, errorUpdateCount, refetch, isFetching } = useHydratedSession();
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- components/auth lib/queries components/layout/AppNav.test.tsx`
Expected: PASS. Les tests existants d'`AppNav` et `UserMenu` montent par `render` (pas d'hydratation) : `useHydrated` y vaut vrai dès le premier rendu, leur comportement ne change pas.

- [ ] **Step 5: Lint and commit**

Run: `npm run lint`
Expected: aucune erreur.

```bash
/usr/bin/git add frontend/lib/queries/auth.ts frontend/lib/queries/hydrated-session.test.tsx frontend/components/layout/AppNav.tsx frontend/components/auth/UserMenu.tsx frontend/components/auth/UserMenu.hydration.test.tsx
```
```bash
/usr/bin/git commit -m "fix(frontend): read the hydrated session in the nav and account menu (#1191)"
```

---

### Task B4: Tuile « Meilleur classement » relative au champ (#1212)

Aujourd'hui la fiche athlète a deux tuiles : « Meilleure place » (rang brut minimum) et « Meilleur ratio » (`Top 14%`, détail `42e sur 300`). Elles deviennent une seule tuile « Meilleur classement » : valeur `3e`, détail `sur 850 · Top 1 %`, résultat choisi au meilleur centile (`bestRatio`), repli sur le meilleur rang brut quand aucun ratio n'est exploitable. Le régime complet passe de cinq à quatre tuiles.

**Files:**
- Modify: `frontend/lib/utils/ranking.ts` (nouvelle fonction `bestRanking` après `bestRatio`)
- Modify: `frontend/app/(public_restricted)/athletes/[id]/page.tsx:56-75,172-204`
- Test: `frontend/lib/utils/ranking.test.ts`
- Test: `frontend/app/(public_restricted)/athletes/[id]/page.test.tsx` (l. 157-200, 470-480, 497-560, 573-575, 600-610)

**Interfaces:**
- Consumes: `bestRatio(parts: Participation[]): RatioEntry | null`, `ordinalFr(n: number): string`, `formatCount(n: number): string` (`lib/utils/format.ts`).
- Produces: `export interface BestRanking { rank: number; total: number | null; percent: number | null }` et `export function bestRanking(parts: Participation[]): BestRanking | null`.

- [ ] **Step 1: Write the failing unit tests**

Dans `frontend/lib/utils/ranking.test.ts`, importer `bestRanking` et ajouter (le helper `part` du fichier construit une `Participation`) :

```ts
describe("bestRanking", () => {
  it("retient le meilleur centile et porte rang, total et pourcentage", () => {
    const best = bestRanking([
      part({ id: 1, rank_overall: 29, course_finishers: 30 }),
      part({ id: 2, rank_overall: 3, course_finishers: 850 }),
      part({ id: 3, rank_overall: 2, course_finishers: 10 }),
    ]);
    expect(best).toEqual({ rank: 3, total: 850, percent: 1 });
  });

  it("retombe sur le meilleur rang brut sans ratio exploitable", () => {
    const best = bestRanking([
      part({ id: 1, rank_overall: 42, course_finishers: 20 }),
      part({ id: 2, rank_overall: 50, course_finishers: null }),
    ]);
    expect(best).toEqual({ rank: 42, total: null, percent: null });
  });

  it("ignore les rangs absents ou nuls et rend null sans rang", () => {
    expect(bestRanking([part({ id: 1, rank_overall: null }), part({ id: 2, rank_overall: 0 })])).toBeNull();
    expect(bestRanking([])).toBeNull();
  });
});
```

Vérifier la signature du helper `part` en tête du fichier (champs acceptés) avant de lancer.

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- lib/utils/ranking.test.ts`
Expected: FAIL, `bestRanking is not a function` (ou erreur d'import).

- [ ] **Step 3: Implement `bestRanking`**

Dans `frontend/lib/utils/ranking.ts`, après `bestRatio` :

```ts
export interface BestRanking {
  rank: number;
  /** Classés de la course, `null` quand le meilleur rang n'a pas de ratio exploitable. */
  total: number | null;
  percent: number | null;
}

/**
 * Meilleur classement rapporté au champ (#1212) : un 29e sur 30 ne vaut pas un
 * 29e sur 2 000. Le résultat retenu est celui du meilleur centile ; sans aucun
 * ratio exploitable (course non fiable, classés inconnus), repli sur le
 * meilleur rang brut, sans dénominateur.
 */
export function bestRanking(parts: Participation[]): BestRanking | null {
  const ratio = bestRatio(parts);
  if (ratio) return { rank: ratio.ratio.rank, total: ratio.ratio.total, percent: ratio.ratio.percent };
  const ranks = parts.map((p) => p.rank_overall).filter((r): r is number => r != null && r >= 1);
  return ranks.length ? { rank: Math.min(...ranks), total: null, percent: null } : null;
}
```

- [ ] **Step 4: Run to verify the unit tests pass**

Run: `npm test -- lib/utils/ranking.test.ts`
Expected: PASS.

- [ ] **Step 5: Rewrite the page tests for the merged tile**

Dans `frontend/app/(public_restricted)/athletes/[id]/page.test.tsx` :

Remplacer le test « retient le meilleur ratio, pas la meilleure place » par :

```tsx
  it("affiche le meilleur classement rapporté au champ (#1212)", async () => {
    await renderAthlete([
      part({ id: 1, rank_overall: 42, course_finishers: 300 }),
      part({ id: 2, rank_overall: 20, course_finishers: 80 }),
      // #488 : le régime complet des tuiles commence à 3 épreuves validées.
      part({ id: 3, rank_overall: 60, course_finishers: 90 }),
    ]);

    // Le meilleur centile est 42e sur 300 (14 %), pas la meilleure place brute (20e sur 80, 25 %).
    const tile = screen.getByText("Meilleur classement").parentElement?.parentElement as HTMLElement;
    expect(within(tile).getByText("42e")).toBeInTheDocument();
    expect(within(tile).getByText("sur 300 · Top 14 %")).toBeInTheDocument();
    expect(screen.queryByText("Meilleure place")).not.toBeInTheDocument();
    expect(screen.queryByText("Meilleur ratio")).not.toBeInTheDocument();
  });
```

Dans « retombe sur la place seule quand le classement est incohérent », remplacer `expect(screen.getByText("Meilleur ratio")).toBeInTheDocument();` par :

```tsx
    const tile = screen.getByText("Meilleur classement").parentElement?.parentElement as HTMLElement;
    expect(within(tile).getByText("42e")).toBeInTheDocument();
    expect(within(tile).queryByText(/sur 20/)).not.toBeInTheDocument();
```

Partout ailleurs :
- `screen.queryByText("Meilleure place")` et `screen.queryByText("Meilleur ratio")` des tests « aucune tuile » et « sous le seuil » : remplacer les deux lignes par `expect(screen.queryByText("Meilleur classement")).not.toBeInTheDocument();`.
- `screen.getByText("Meilleure place").parentElement?.parentElement` : remplacer par `screen.getByText("Meilleur classement").parentElement?.parentElement`, et la valeur attendue `"5"` par `"5e"` (« compte les StatCard… », « ne tient pas compte d'un relais… », « écarte aussi un relais… »).
- Dans « ne tient pas compte d'un relais… », remplacer le bloc `ratioCard` par :

```tsx
    expect(within(placeCard as HTMLElement).getByText("sur 50 · Top 10 %, hors relais")).toBeInTheDocument();
```
et retirer l'assertion `within(placeCard).getByText("Hors relais")` (le repère est désormais dans le détail).
- « au seuil, retrouve les cinq tuiles » devient « au seuil, retrouve les quatre tuiles » avec `["Épreuves", "Meilleur classement", "Top 10", "Format favori"]`.

- [ ] **Step 6: Run to verify the page tests fail**

Run: `npm test -- "app/(public_restricted)/athletes/[id]/page.test.tsx"`
Expected: FAIL, `Unable to find an element with the text: Meilleur classement`.

- [ ] **Step 7: Rewrite the tiles in the page**

Dans `page.tsx` : import `bestRanking` à la place de `bestRatio` (l. 19) et `formatCount` avec `ordinalFr` depuis `@/lib/utils/format` (l. 16). Remplacer `const best = …` (l. 63) et `const topRatio = bestRatio(individuels);` (l. 74) par :

```ts
  const best = bestRanking(individuels);
```

Garder `places` et `top10` tels quels. Puis remplacer les deux `StatCard` « Meilleure place » et « Meilleur ratio » par :

```tsx
            <StatCard
              label="Meilleur classement"
              value={best ? ordinalFr(best.rank) : "—"}
              // Rapporté au champ (#1212) : un 29e sur 30 n'est pas un 29e sur 2 000.
              hint={
                best?.total != null
                  ? `sur ${formatCount(best.total)} · Top ${best.percent} %${horsRelais ? ", hors relais" : ""}`
                  : horsRelais
              }
              valueColor="var(--tcn-orange)"
              accent={false}
            />
```

Et la grille passe à quatre colonnes au plus large : `className="grid grid-cols-2 gap-4 lg:grid-cols-4"`.

Note : ` ` (espace insécable avant `%`) ne s'écrit pas dans les assertions `getByText("… Top 14 %")` du Step 5 avec une espace ordinaire : `getByText` normalise les espaces par défaut (`\s+` couvre ` `), vérifier au Step 8 ; si l'assertion échoue, écrire `"sur 300 · Top 14 %"` dans les tests.

- [ ] **Step 8: Run to verify the page tests pass**

Run: `npm test -- "app/(public_restricted)/athletes/[id]/page.test.tsx" lib/utils/ranking.test.ts lib/utils/athlete-stats.test.ts`
Expected: PASS.

- [ ] **Step 9: Lint, build, commit**

Run: `npm run lint` puis `npm run build`
Expected: aucune erreur ESLint, build Next.js réussi (strict TS).

```bash
/usr/bin/git add frontend/lib/utils/ranking.ts frontend/lib/utils/ranking.test.ts "frontend/app/(public_restricted)/athletes/[id]/page.tsx" "frontend/app/(public_restricted)/athletes/[id]/page.test.tsx"
```
```bash
/usr/bin/git commit -m "feat(athletes): express the best ranking relative to the field size (#1212)"
```


# Partie C

## Part C: stored TCN counting rule and ambiguous labels (#1206)

Spec: section 5 « Colonne et règle » and « Libellés ambigus (#1206) ».
Part D (club members) **extends** the rule written here; the hook points are
named in Task C3 (`_rule`, `_attached_to_club`, `_scope`) and must stay the
only places where the rule is written.

**Design decisions locked by this part (read before any task):**

- `core.club.is_tcn(club)` keeps its meaning: « this label belongs to the
  scope », ambiguous labels included. It still serves the scrapers (which TCN
  rows get a detail page), `club_alias` (refusing a TCN label as alias) and the
  `club-labels` CLI. **Counting** never uses it again: counting reads
  `Participation.counts_for_tcn`.
- The registry (`core/counter_scope.py`) gains a third set, the ambiguous
  labels. Its **default is empty**: the registry defaults stay « the values
  from before the switch » (doctrine of that module), so every existing test
  that writes `club="TCN"` keeps counting it. Production gets `tcn` ambiguous
  from the migration, then `load_from_db`.
- A mapper listener sets `counts_for_tcn` from condition 1 alone (label in scope
  and not ambiguous, read from the registry) on insert and whenever `club`
  changes. The full SQL rule (conditions 1 and 3, then part D's condition 2) is
  applied by `tcn_count_repository.recompute_counts_for_tcn` at every trigger.
  The listener is what keeps the ~33 test files that create rows directly
  through `participation_repository.create` correct without a recompute.
- `recompute_counts_for_tcn(db, *, course_ids=None, athlete_ids=None, labels=None)`:
  `labels=None` reads the registry (import path, admin gestures); the counter
  scope service passes labels re-read in its transaction (same reason as
  `tcn_clause(..., labels)` today, #939). The third keyword is an addition to
  the fixed interface, not a change of it.
- After its bulk `UPDATE`s the repository expires `counts_for_tcn` on loaded
  `Participation` instances and `tcn_count` on loaded `Course` instances, so a
  route serializing an object it already holds never serves a stale verdict.

**Readers repointed to `Participation.counts_for_tcn.is_(True)`** (every
`tcn_clause(Participation.club)` of the codebase, line numbers on `main` at
`76084c80`):

| File | Line | Function |
| --- | --- | --- |
| `backend/app/repositories/participation_repository.py` | 320 | `count_bibs_absent_from` |
| same | 498 | `_apply_filters` |
| same | 845 | `list_page_for_course` |
| same | 931 | `_stats_filters` |
| same | 1123 | `club_podiums` |
| same | 1165 | `_grouped_events_query` |
| same | 1441 | `distinct_seasons` |
| `backend/app/repositories/course_repository.py` | 507 | `recount` |
| same | 566 | `recompute_tcn_counts_all` (deleted, replaced by the new repository) |
| same | 622 | `_filtered` |
| same | 775 | duplicates query |
| `backend/app/repositories/athlete_repository.py` | 736 | `list_with_season_participation_count` |
| same | 866 | `_club_roster_requete` |
| same | 940 | `club_composition` |
| same | 993 | `club_records_with_two_bibs_on_a_race` (`_club_flag(Participation.club)`) |
| same | 1020 | `homonym_groups` |

Python readers repointed: `schemas/participation.py:61-70` (`ParticipationOut.is_tcn`),
`services/stats_service.py:308,315,365` (`course_summary`),
`services/admin_actions.py:948,1073`, `services/opposition_service.py:167`.
`ParticipationOut`/`AthleteParticipationOut` are only built by
`model_validate(<ORM Participation>)` (`api/v1/athletes.py:135`,
`api/v1/courses.py:265`, `api/v1/participations.py:142`, and FastAPI on
`response_model=list[ParticipationOut]` routes): no site builds them from a
dict, so reading the ORM attribute is safe.

**Unchanged on purpose:** `tcn_clause(Athlete.club)` at
`athlete_repository.py:478,747,830,1022`, `_club_filter_targets`
(`participation_repository.py:773,785`, a label filter), the scrapers'
`is_tcn`, `club_alias`, `cli/commands/club_labels.py`. Follow-up issue (spec,
« Hors périmètre »).

---

### Task C1: Ambiguous labels in the registry and `ClubLabels`

**Files:**
- Modify: `backend/app/core/counter_scope.py`
- Modify: `backend/app/core/club.py`
- Test: `backend/tests/test_core/test_counter_scope.py`
- Test: `backend/tests/test_core/test_club.py`

**Interfaces:**
- Produces: `counter_scope.ambiguous_club_labels() -> frozenset[str]`;
  `counter_scope.load(*, disciplines, club_labels, ambiguous_club_labels=()) -> None`;
  `club.ClubLabels(clear: frozenset[str], ambiguous: frozenset[str])` with
  `ClubLabels.from_registry() -> ClubLabels`,
  `ClubLabels.from_entries(entries: Iterable[tuple[str, bool]]) -> ClubLabels`
  (pairs `(normalized value, ambiguous)`), `ClubLabels.counts_by_label(club: str | None) -> bool`;
  `club.counts_by_label(club: str | None) -> bool` (registry shortcut).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_core/test_counter_scope.py`:

```python
def test_no_label_is_ambiguous_by_default():
    assert counter_scope.ambiguous_club_labels() == frozenset()


def test_load_replaces_the_ambiguous_labels_with_the_two_other_sets():
    counter_scope.load(
        disciplines={"trail"}, club_labels={"tcn", "tri club nantais"}, ambiguous_club_labels={"tcn"}
    )

    assert counter_scope.ambiguous_club_labels() == frozenset({"tcn"})
    assert counter_scope.tcn_club_labels() == frozenset({"tcn", "tri club nantais"})


def test_load_without_ambiguous_labels_clears_them():
    counter_scope.load(disciplines=set(), club_labels={"tcn"}, ambiguous_club_labels={"tcn"})
    counter_scope.load(disciplines=set(), club_labels={"tcn"})

    assert counter_scope.ambiguous_club_labels() == frozenset()


def test_reset_clears_the_ambiguous_labels():
    counter_scope.load(disciplines=set(), club_labels={"tcn"}, ambiguous_club_labels={"tcn"})

    counter_scope.reset()

    assert counter_scope.ambiguous_club_labels() == frozenset()
```

Append to `backend/tests/test_core/test_club.py`:

```python
from app.core import counter_scope
from app.core.club import ClubLabels, counts_by_label


def test_club_labels_split_clear_and_ambiguous_entries():
    labels = ClubLabels.from_entries([("tcn", True), ("tri club nantais", False)])

    assert labels.clear == frozenset({"tri club nantais"})
    assert labels.ambiguous == frozenset({"tcn"})


def test_an_ambiguous_label_does_not_count_by_its_label_alone():
    labels = ClubLabels(clear=frozenset({"tri club nantais"}), ambiguous=frozenset({"tcn"}))

    assert labels.counts_by_label("  TRI  Club Nantais ") is True
    assert labels.counts_by_label("TCN") is False
    assert labels.counts_by_label("ASPTT") is False
    assert labels.counts_by_label(None) is False


def test_from_registry_reads_the_three_sets():
    counter_scope.load(
        disciplines=set(), club_labels={"tcn", "tri club nantais"}, ambiguous_club_labels={"tcn"}
    )

    assert ClubLabels.from_registry() == ClubLabels(
        clear=frozenset({"tri club nantais"}), ambiguous=frozenset({"tcn"})
    )
    assert counts_by_label("TCN") is False
    assert counts_by_label("Tri Club Nantais") is True


def test_an_ambiguous_label_outside_the_scope_is_ignored():
    counter_scope.load(disciplines=set(), club_labels={"tri club nantais"}, ambiguous_club_labels={"tcn"})

    assert ClubLabels.from_registry().ambiguous == frozenset()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_core/test_counter_scope.py tests/test_core/test_club.py -n 0`
Expected: FAIL (`AttributeError: ... ambiguous_club_labels`, `ImportError: cannot import name 'ClubLabels'`).

- [ ] **Step 3: Implement**

In `backend/app/core/counter_scope.py`, replace the `_scope` declaration and
everything below it with:

```python
#: Les trois ensembles dans **un seul nom** : `(disciplines, libellés,
#: libellés ambigus)`. Deux variables auraient donné deux affectations, donc une
#: fenêtre (courte, mais réelle) où un lecteur voit les nouvelles disciplines et
#: les anciens libellés. Un seul nom rend le remplacement atomique pour de bon.
#:
#: Aucun libellé n'est ambigu par défaut : les défauts restent les valeurs
#: d'avant la bascule, et c'est la migration qui marque « tcn » ambigu en base
#: (#1206).
_scope: tuple[frozenset[str], frozenset[str], frozenset[str]] = (
    DEFAULT_NON_FEDERAL_DISCIPLINES,
    DEFAULT_TCN_CLUB_LABELS,
    frozenset(),
)


def non_federal_disciplines() -> frozenset[str]:
    """Les disciplines exclues des compteurs, en vigueur."""
    return _scope[0]


def tcn_club_labels() -> frozenset[str]:
    """Les libellés reconnus comme libellés du club, en vigueur, ambigus compris."""
    return _scope[1]


def ambiguous_club_labels() -> frozenset[str]:
    """Les libellés du club qui désignent aussi d'autres clubs (#1206).

    Un résultat qui ne porte que l'un d'eux ne compte pour le club que si son
    athlète y est rattaché par ailleurs (`repositories/tcn_count_repository`).
    """
    return _scope[2]


def load(
    *,
    disciplines: Iterable[str],
    club_labels: Iterable[str],
    ambiguous_club_labels: Iterable[str] = (),
) -> None:
    """Remplace les trois ensembles d'un seul geste, **par réassignation**.

    Deux propriétés, et les deux comptent.

    Les ensembles ensemble : ils tiennent dans un seul nom, donc une
    configuration à moitié rechargée est un état que rien ne peut produire.

    Par réassignation, jamais par mutation en place (`add`, `discard`, `clear`) :
    l'import d'épreuve tourne dans un **thread d'arrière-plan** (le scrape SSE)
    et lit ce registre ligne par ligne pendant qu'un administrateur peut écrire.
    Réassigner un nom est atomique du point de vue de ce thread ; muter en place
    lui exposerait un ensemble à moitié écrit, et le résultat serait quelques
    lignes mal classées, sans erreur ni trace.
    """
    global _scope
    _scope = (frozenset(disciplines), frozenset(club_labels), frozenset(ambiguous_club_labels))


def reset() -> None:
    """Retour aux défauts : fixture de test, et rien d'autre."""
    load(disciplines=DEFAULT_NON_FEDERAL_DISCIPLINES, club_labels=DEFAULT_TCN_CLUB_LABELS)
```

In `backend/app/core/club.py`, add `from dataclasses import dataclass` to the
imports and insert after `is_tcn`:

```python
@dataclass(frozen=True)
class ClubLabels:
    """Les libellés de la portée, séparés selon qu'ils suffisent ou non (#1206).

    `clear` : un résultat qui porte l'un d'eux compte pour le club.
    `ambiguous` : le libellé désigne aussi d'autres clubs (« TCN » est aussi le
    Triathlon Club Narbonne) ; il ne compte que si l'athlète est rattaché au club
    par ailleurs, ce que seule la base sait dire
    (`repositories/tcn_count_repository`).
    """

    clear: frozenset[str]
    ambiguous: frozenset[str]

    @classmethod
    def from_registry(cls) -> "ClubLabels":
        labels = counter_scope.tcn_club_labels()
        ambiguous = counter_scope.ambiguous_club_labels() & labels
        return cls(clear=labels - ambiguous, ambiguous=ambiguous)

    @classmethod
    def from_entries(cls, entries: Iterable[tuple[str, bool]]) -> "ClubLabels":
        """Depuis des couples `(valeur normalisée, ambiguë)` relus en base."""
        pairs = list(entries)
        return cls(
            clear=frozenset(value for value, ambiguous in pairs if not ambiguous),
            ambiguous=frozenset(value for value, ambiguous in pairs if ambiguous),
        )

    def counts_by_label(self, club: str | None) -> bool:
        """Le libellé suffit-il, à lui seul, à compter le résultat pour le club ?"""
        return normalize_club(club) in self.clear


def counts_by_label(club: str | None) -> bool:
    """`ClubLabels.counts_by_label` sur la configuration en vigueur.

    Seul lecteur : l'écouteur de `models/participation.py`, qui pose la valeur
    de départ de `counts_for_tcn` sans Session.
    """
    return ClubLabels.from_registry().counts_by_label(club)
```

Also replace the `is_tcn` docstring first line with:
`"""Vrai si \`club\` est un libellé de la portée du club, ambigu compris.` and
add to its body: `Ce verdict ne compte rien : un résultat compte pour le club
selon \`Participation.counts_for_tcn\` (#1206).`

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_core -n 0`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/core/counter_scope.py backend/app/core/club.py backend/tests/test_core/test_counter_scope.py backend/tests/test_core/test_club.py
/usr/bin/git commit -m "feat(core): ambiguous club labels in the counter scope registry (#1206)"
```

---

### Task C2: Columns, listener and migration

**Files:**
- Modify: `backend/app/models/participation.py`
- Modify: `backend/app/models/counter_scope_entry.py`
- Modify: `backend/app/services/counter_scope.py` (`load_from_db`)
- Create: `backend/alembic/versions/c4f1a7d2e9b3_counts_for_tcn.py`
- Test: `backend/tests/test_repositories/test_tcn_count_repository.py` (created here, completed in C3)
- Test: `backend/tests/test_services/test_counter_scope.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `club.counts_by_label` (C1).
- Produces: `Participation.counts_for_tcn: Mapped[bool]` (non null, default
  `False`, index `ix_participations_counts_for_tcn`), set by the listener on
  insert and on a `club` change; `CounterScopeEntry.ambiguous: Mapped[bool]`
  (non null, default `False`); `load_from_db` loads the ambiguous set.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_repositories/test_tcn_count_repository.py`:

```python
"""Stored TCN counting rule (#1206): `Participation.counts_for_tcn`."""
from datetime import date

from app.core import counter_scope
from app.repositories import athlete_repository, course_repository, participation_repository


def _course(db, name="Tri de test", day=18):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 5, day), event_type="triathlon-m"
    )


def _result(db, athlete, course, bib, club, *, pending=False):
    return participation_repository.create(
        db,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number=bib,
        club=club,
        is_pending_validation=pending,
    )


def _ambiguous_tcn():
    counter_scope.load(
        disciplines=counter_scope.non_federal_disciplines(),
        club_labels=counter_scope.tcn_club_labels(),
        ambiguous_club_labels={"tcn"},
    )


def test_a_new_row_takes_its_label_verdict(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    course = _course(db_session)

    nantes = _result(db_session, athlete, course, "1", "Triathlon Club Nantais")
    autre = _result(db_session, athlete, _course(db_session, "Autre"), "2", "ASPTT")

    assert nantes.counts_for_tcn is True
    assert autre.counts_for_tcn is False


def test_a_new_row_with_an_ambiguous_label_does_not_count_yet(db_session):
    _ambiguous_tcn()
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")

    row = _result(db_session, athlete, _course(db_session), "1", "TCN")

    assert row.counts_for_tcn is False


def test_changing_the_club_recomputes_the_label_verdict(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _course(db_session), "1", "ASPTT")

    participation_repository.update(db_session, row, club="Tri Club Nantais")

    assert row.counts_for_tcn is True
```

Append to `backend/tests/test_services/test_counter_scope.py`:

```python
def test_load_from_db_loads_the_ambiguous_labels(db_session):
    from app.core import counter_scope as registre
    from app.repositories import counter_scope_repository

    tcn = counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="tcn", created_by_user_id=None
    )
    tcn.ambiguous = True
    counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="tri club nantais", created_by_user_id=None
    )
    db_session.flush()

    counter_scope.load_from_db(db_session)

    assert registre.tcn_club_labels() == frozenset({"tcn", "tri club nantais"})
    assert registre.ambiguous_club_labels() == frozenset({"tcn"})
```

Append to `backend/tests/test_migrations.py` (reuses `_alembic_config`,
`_lignes`, `sqlite_url`, `get_settings`, `sa` already imported there):

```python
_BEFORE_COUNTS_FOR_TCN = "baef0d35bb4f"


def test_counts_for_tcn_backfill_applies_the_rule(sqlite_url, monkeypatch):
    """#1206: `tcn` becomes ambiguous; a bare `TCN` counts only when the athlete
    has another validated result under a clear label."""
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    get_settings.cache_clear()
    cfg = _alembic_config()
    command.upgrade(cfg, _BEFORE_COUNTS_FOR_TCN)
    engine = sa.create_engine(sqlite_url)
    with engine.begin() as connexion:
        connexion.execute(sa.text(
            "INSERT INTO athletes (id, nom, prenom, gender, club_locked, created_at, homonym_rank)"
            " VALUES (1, 'MARTIN', 'Anne', '', 0, '2026-01-01', 0),"
            " (2, 'DURAND', 'Paul', '', 0, '2026-01-01', 0)"
        ))
        connexion.execute(sa.text(
            "INSERT INTO courses (id, name, event_date, event_type, is_relay, ranked_by_laps,"
            " created_at, participation_count, tcn_count)"
            " VALUES (1, 'A', '2026-05-01', 'triathlon-m', 0, 0, '2026-01-01', 0, 0),"
            " (2, 'B', '2026-06-01', 'triathlon-m', 0, 0, '2026-01-01', 0, 0)"
        ))
        connexion.execute(sa.text(
            "INSERT INTO participations (id, athlete_id, course_id, club, bib_number, status,"
            " is_relay, is_pending_validation, is_rejected, athlete_locked, created_at) VALUES"
            " (1, 1, 1, 'TCN', '1', 'finisher', 0, 0, 0, 0, '2026-01-01'),"
            " (2, 1, 2, 'Triathlon Club Nantais', '1', 'finisher', 0, 0, 0, 0, '2026-01-01'),"
            " (3, 2, 1, 'TCN', '2', 'finisher', 0, 0, 0, 0, '2026-01-01')"
        ))
    engine.dispose()

    command.upgrade(cfg, "head")
    get_settings.cache_clear()

    assert _lignes(
        sqlite_url, "SELECT value, ambiguous FROM counter_scope_entries"
        " WHERE kind = 'tcn_club_label' ORDER BY value"
    ) == [("tcn", 1), ("tri club nantais", 0), ("triathlon club nantais", 0)]
    assert _lignes(
        sqlite_url, "SELECT id, counts_for_tcn FROM participations ORDER BY id"
    ) == [(1, 1), (2, 1), (3, 0)]
    assert _lignes(sqlite_url, "SELECT id, tcn_count FROM courses ORDER BY id") == [(1, 1), (2, 1)]


def test_downgrade_then_upgrade_of_counts_for_tcn(sqlite_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    get_settings.cache_clear()
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, _BEFORE_COUNTS_FOR_TCN)
    assert "counts_for_tcn" not in _columns(sqlite_url, "participations")
    assert "ambiguous" not in _columns(sqlite_url, "counter_scope_entries")
    command.upgrade(cfg, "head")
    get_settings.cache_clear()
    assert "counts_for_tcn" in _columns(sqlite_url, "participations")
```

Before Step 2, check the exact non-null columns of `athletes`, `courses` and
`participations` at `baef0d35bb4f` (`uv run python -c "import sqlalchemy as sa; ..."`
or read the models) and adjust the three `INSERT` column lists so they satisfy
every `NOT NULL` without a server default; the values of the rule columns
(`club`, `is_pending_validation`, `athlete_id`, `course_id`) stay as written.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_tcn_count_repository.py tests/test_services/test_counter_scope.py tests/test_migrations.py -n 0`
Expected: FAIL (`counts_for_tcn` / `ambiguous` unknown; migration missing).

- [ ] **Step 3: Implement**

`backend/app/models/counter_scope_entry.py`: add `Boolean, false` to the
`sqlalchemy` import and, after `value`:

```python
    #: Libellé qui désigne aussi d'autres clubs (#1206) : « TCN » est aussi le
    #: Triathlon Club Narbonne. Un résultat qui ne porte que lui ne compte pour le
    #: club que si son athlète y est rattaché par ailleurs. N'a de sens que pour
    #: un libellé de club.
    ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false(), default=False)
```

`backend/app/models/participation.py`: add `event` to the `sqlalchemy` import,
`from app.core.club import CLUB_NORMALIZED_INDEX_EXPRESSION, counts_by_label`,
and after `athlete_locked`:

```python
    # Ce résultat compte-t-il pour le club (#1206) ? Seule lecture des compteurs,
    # statistiques et du badge `is_tcn`. Écrit par `repositories/
    # tcn_count_repository.recompute_counts_for_tcn`, qui applique la règle
    # entière ; l'écouteur plus bas n'en pose que la première condition, à la
    # création et à chaque changement de `club`.
    counts_for_tcn: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false(), default=False, index=True
    )
```

At the end of the module:

```python
@event.listens_for(Participation, "before_insert")
def _counts_for_tcn_on_insert(mapper, connection, target: Participation) -> None:
    target.counts_for_tcn = counts_by_label(target.club)


@event.listens_for(Participation, "before_update")
def _counts_for_tcn_on_club_change(mapper, connection, target: Participation) -> None:
    # Seule la condition du libellé se juge sans Session : le rattachement par
    # un autre résultat (et la licence, #1202) attend le recalcul que chaque
    # chemin d'écriture déclenche ensuite.
    if inspect(target).attrs.club.history.has_changes():
        target.counts_for_tcn = counts_by_label(target.club)
```

(add `inspect` to the `sqlalchemy` import.)

`backend/app/services/counter_scope.py`, `load_from_db`:

```python
def load_from_db(db: Session) -> None:
    """Relit les listes en base et remplace le registre d'un seul geste."""
    entries = counter_scope_repository.list_entries(db)
    counter_scope.load(
        disciplines={e.value for e in entries if e.kind == NON_FEDERAL_DISCIPLINE},
        club_labels={e.value for e in entries if e.kind == CLUB_LABEL},
        ambiguous_club_labels={e.value for e in entries if e.kind == CLUB_LABEL and e.ambiguous},
    )
```

Create `backend/alembic/versions/c4f1a7d2e9b3_counts_for_tcn.py` (if
`uv run alembic heads` shows another head than `baef0d35bb4f`, set
`down_revision` to it and `_BEFORE_COUNTS_FOR_TCN` in the test accordingly):

```python
"""counts_for_tcn and ambiguous club labels (#1206)

Un libellé « TCN » seul est aussi celui du Triathlon Club Narbonne : la portée
gagne un drapeau `ambiguous`, posé ici sur `tcn`, et chaque résultat porte son
verdict dans `participations.counts_for_tcn`. Le backfill applique la règle en
SQL, **figée ici** : un libellé non ambigu de la portée compte ; un libellé
ambigu compte si l'athlète a un autre résultat validé sous un libellé non
ambigu. Puis `courses.tcn_count` est recalculé depuis la colonne.

Revision ID: c4f1a7d2e9b3
Revises: baef0d35bb4f
Create Date: 2026-10-06 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.club import CLUB_NORMALIZED_INDEX_EXPRESSION, _normalise_sql

revision: str = 'c4f1a7d2e9b3'
down_revision: Union[str, None] = 'baef0d35bb4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # `op.add_column` et non `batch_alter_table` : sur SQLite, le batch recrée la
    # table et perd l'index fonctionnel du club (cf. `05094fea3bc2`).
    op.add_column(
        'counter_scope_entries',
        sa.Column('ambiguous', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        'participations',
        sa.Column('counts_for_tcn', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index('ix_participations_counts_for_tcn', 'participations', ['counts_for_tcn'])

    entries = sa.table(
        'counter_scope_entries', sa.column('kind'), sa.column('value'), sa.column('ambiguous')
    )
    op.execute(
        entries.update()
        .where(entries.c.kind == 'tcn_club_label', entries.c.value == 'tcn')
        .values(ambiguous=True)
    )

    connexion = op.get_bind()
    rows = connexion.execute(
        sa.select(entries.c.value, entries.c.ambiguous).where(entries.c.kind == 'tcn_club_label')
    ).all()
    clear = sorted(value for value, ambiguous in rows if not ambiguous)
    ambiguous = sorted(value for value, ambiguous in rows if ambiguous)

    p = sa.table(
        'participations',
        sa.column('id'), sa.column('athlete_id'), sa.column('course_id'), sa.column('club'),
        sa.column('is_pending_validation'), sa.column('counts_for_tcn'),
    )
    other = p.alias('other')
    attached = (
        sa.select(sa.literal(1))
        .select_from(other)
        .where(
            other.c.athlete_id == p.c.athlete_id,
            other.c.id != p.c.id,
            other.c.is_pending_validation.is_(False),
            _normalise_sql(other.c.club).in_(clear),
        )
        .exists()
    )
    rule = sa.or_(
        _normalise_sql(p.c.club).in_(clear),
        sa.and_(_normalise_sql(p.c.club).in_(ambiguous), attached),
    )
    op.execute(p.update().values(counts_for_tcn=sa.case((rule, True), else_=False)))

    courses = sa.table('courses', sa.column('id'), sa.column('tcn_count'))
    counted = (
        sa.select(sa.func.count(p.c.id))
        .where(
            p.c.course_id == courses.c.id,
            p.c.is_pending_validation.is_(False),
            p.c.counts_for_tcn.is_(True),
        )
        .scalar_subquery()
    )
    op.execute(courses.update().values(tcn_count=counted))


def downgrade() -> None:
    op.drop_index('ix_participations_counts_for_tcn', table_name='participations')
    with op.batch_alter_table('participations', schema=None) as batch_op:
        batch_op.drop_column('counts_for_tcn')
    with op.batch_alter_table('counter_scope_entries', schema=None) as batch_op:
        batch_op.drop_column('ambiguous')
    # Le batch SQLite a recréé `participations` sans l'index fonctionnel.
    if op.get_bind().dialect.name == "sqlite":
        op.create_index(
            "ix_participations_club_normalized",
            "participations",
            [sa.text(CLUB_NORMALIZED_INDEX_EXPRESSION)],
        )
```

Check the downgrade on a migrated SQLite base: if `drop_index` fails because
the index name differs once reflected, read it with
`sa.inspect(engine).get_indexes('participations')` and use the reflected name.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_tcn_count_repository.py tests/test_services/test_counter_scope.py tests/test_migrations.py -n 0`
Expected: PASS. Then the whole suite: `cd backend && uv run pytest -m "not integration"`; expected PASS (no reader uses the column yet).

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/models/participation.py backend/app/models/counter_scope_entry.py backend/app/services/counter_scope.py backend/alembic/versions/c4f1a7d2e9b3_counts_for_tcn.py backend/tests/test_repositories/test_tcn_count_repository.py backend/tests/test_services/test_counter_scope.py backend/tests/test_migrations.py
/usr/bin/git commit -m "feat(models): store counts_for_tcn and mark tcn as an ambiguous label (#1206)"
```

---

### Task C3: `tcn_count_repository.recompute_counts_for_tcn`

**Files:**
- Create: `backend/app/repositories/tcn_count_repository.py`
- Modify: `backend/app/repositories/course_repository.py` (`recount` reads the
  column; delete `recompute_tcn_counts_all`)
- Test: `backend/tests/test_repositories/test_tcn_count_repository.py`
- Modify test: `backend/tests/test_repositories/test_course_repository.py`
  (delete `test_recompute_tcn_counts_rewrites_only_the_courses_whose_count_changes`,
  superseded by the tests below)

**Interfaces:**
- Consumes: `ClubLabels` (C1), the columns (C2).
- Produces:
  `recompute_counts_for_tcn(db: Session, *, course_ids: Iterable[int] | None = None, athlete_ids: Iterable[int] | None = None, labels: ClubLabels | None = None) -> None`.
  Both ids `None`: every participation and every course. Otherwise the scope is
  the union of: participations of `course_ids`, every participation of the
  athletes who have one on `course_ids` (condition 3 crosses courses), and
  participations of `athlete_ids`. `Course.tcn_count` is then recounted for the
  courses of the scope **plus** `course_ids` (a course whose rows were just
  deleted). `labels=None` reads the registry.
- **Part D hook points** (private, same module): `_rule(labels) ->
  ColumnElement[bool]` (part D adds the « licencié de la saison » branch, with
  the teammates join), `_attached_to_club(labels) -> ColumnElement[bool]` (part
  D ORs « licence rattachée, toute saison »), `_scope(course_ids, athlete_ids)`
  (part D adds the participations where a scoped athlete is a teammate).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_repositories/test_tcn_count_repository.py`:

```python
from app.core.club import ClubLabels
from app.repositories import tcn_count_repository

_LABELS = ClubLabels(clear=frozenset({"triathlon club nantais"}), ambiguous=frozenset({"tcn"}))


def _flags(db, *rows):
    db.expire_all()
    return [row.counts_for_tcn for row in rows]


def test_an_ambiguous_label_alone_does_not_count(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    row = _result(db_session, athlete, _course(db_session), "1", "TCN")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, row) == [False]


def test_an_ambiguous_label_counts_when_the_athlete_has_a_clear_result(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    clear = _result(db_session, athlete, _course(db_session, "B"), "1", "Triathlon Club Nantais")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, bare, clear) == [True, True]


def test_a_pending_clear_result_does_not_confirm_the_club(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    _result(db_session, athlete, _course(db_session, "B"), "1", "Triathlon Club Nantais", pending=True)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, bare) == [False]


def test_a_label_outside_the_scope_never_counts(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    _result(db_session, athlete, _course(db_session, "A"), "1", "Triathlon Club Nantais")
    other = _result(db_session, athlete, _course(db_session, "B"), "1", "ASPTT")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert _flags(db_session, other) == [False]


def test_the_course_counter_counts_validated_flagged_rows(db_session):
    course = _course(db_session)
    for bib, (nom, club, pending) in enumerate(
        [("A", "Triathlon Club Nantais", False), ("B", "TCN", False), ("C", "Triathlon Club Nantais", True)]
    ):
        athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="X")
        _result(db_session, athlete, course, str(bib), club, pending=pending)

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    db_session.expire_all()
    assert course.tcn_count == 1


def test_a_course_scope_reaches_the_other_results_of_its_athletes(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    old_course = _course(db_session, "Ancienne", day=1)
    bare = _result(db_session, athlete, old_course, "1", "TCN")
    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)
    new_course = _course(db_session, "Nouvelle", day=20)
    _result(db_session, athlete, new_course, "1", "Triathlon Club Nantais")

    tcn_count_repository.recompute_counts_for_tcn(
        db_session, course_ids=[new_course.id], labels=_LABELS
    )

    assert _flags(db_session, bare) == [True]
    assert old_course.tcn_count == 1


def test_an_athlete_scope_leaves_other_athletes_alone(db_session):
    anne = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    paul = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Paul")
    course = _course(db_session)
    _result(db_session, anne, course, "1", "Triathlon Club Nantais")
    stale = _result(db_session, paul, course, "2", "ASPTT")
    db_session.query(type(stale)).filter_by(id=stale.id).update({"counts_for_tcn": True})

    tcn_count_repository.recompute_counts_for_tcn(db_session, athlete_ids=[anne.id], labels=_LABELS)

    assert _flags(db_session, stale) == [True]


def test_a_course_whose_rows_were_deleted_is_recounted(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    course = _course(db_session)
    row = _result(db_session, athlete, course, "1", "Triathlon Club Nantais")
    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)
    participation_repository.delete(db_session, row)
    db_session.flush()

    tcn_count_repository.recompute_counts_for_tcn(
        db_session, course_ids=[course.id], athlete_ids=[athlete.id], labels=_LABELS
    )

    db_session.expire_all()
    assert course.tcn_count == 0


def test_without_labels_the_registry_decides(db_session):
    _ambiguous_tcn()
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    _result(db_session, athlete, _course(db_session, "B"), "1", "Tri Club Nantais")

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert _flags(db_session, bare) == [True]


def test_loaded_instances_see_the_new_verdict_without_a_refresh(db_session):
    athlete = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Anne")
    bare = _result(db_session, athlete, _course(db_session, "A"), "1", "TCN")
    _result(db_session, athlete, _course(db_session, "B"), "1", "Triathlon Club Nantais")

    tcn_count_repository.recompute_counts_for_tcn(db_session, labels=_LABELS)

    assert bare.counts_for_tcn is True
```

Check `participation_repository.delete` exists (it is called by
`admin_actions.delete_participation`); if its name differs, use the real one.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_tcn_count_repository.py -n 0`
Expected: FAIL (`ImportError: cannot import name 'tcn_count_repository'`).

- [ ] **Step 3: Implement**

Create `backend/app/repositories/tcn_count_repository.py`:

```python
"""Ce qui compte pour le club : la règle, et son seul point d'écriture (#1206).

`Participation.counts_for_tcn` porte le verdict de chaque résultat, et
`Course.tcn_count` en est le compte dénormalisé (#623). Les deux ne s'écrivent
qu'ici, en SQL, portable SQLite (dev, tests) et PostgreSQL (prod).

Un résultat compte pour le club si :

1. son libellé est dans la portée et n'est pas ambigu ;
2. (#1202, partie D) ;
3. son libellé est ambigu (« TCN », aussi le Triathlon Club Narbonne) et son
   athlète est rattaché au club par ailleurs : un autre résultat **validé**
   sous un libellé non ambigu.

Points d'extension de la partie D : `_rule`, `_attached_to_club`, `_scope`.
Nulle part ailleurs la règle ne s'écrit.
"""
from collections.abc import Iterable

from sqlalchemy import and_, case, false, func, literal, or_, select, update
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.elements import ColumnElement

from app.core.club import ClubLabels, _normalise_sql
from app.core.validation import validated_clause
from app.models.course import Course
from app.models.participation import Participation


def _clear_label(club, labels: ClubLabels) -> ColumnElement[bool]:
    return _normalise_sql(club).in_(sorted(labels.clear))


def _ambiguous_label(club, labels: ClubLabels) -> ColumnElement[bool]:
    return _normalise_sql(club).in_(sorted(labels.ambiguous))


def _attached_to_club(labels: ClubLabels) -> ColumnElement[bool]:
    """Condition 3 : l'athlète de la ligne est rattaché au club par ailleurs."""
    other = aliased(Participation)
    return (
        select(literal(1))
        .where(
            other.athlete_id == Participation.athlete_id,
            other.id != Participation.id,
            validated_clause(other.is_pending_validation),
            _clear_label(other.club, labels),
        )
        .correlate(Participation)
        .exists()
    )


def _rule(labels: ClubLabels) -> ColumnElement[bool]:
    return or_(
        _clear_label(Participation.club, labels),
        and_(_ambiguous_label(Participation.club, labels), _attached_to_club(labels)),
    )


def _scope(course_ids: list[int] | None, athlete_ids: list[int] | None) -> ColumnElement[bool] | None:
    """`None` : toutes les lignes. Sinon l'union décrite par `recompute_counts_for_tcn`."""
    if course_ids is None and athlete_ids is None:
        return None
    conditions = []
    if course_ids:
        on_courses = aliased(Participation)
        conditions += [
            Participation.course_id.in_(course_ids),
            Participation.athlete_id.in_(
                select(on_courses.athlete_id).where(on_courses.course_id.in_(course_ids))
            ),
        ]
    if athlete_ids:
        conditions.append(Participation.athlete_id.in_(athlete_ids))
    return or_(*conditions) if conditions else false()


def recompute_counts_for_tcn(
    db: Session,
    *,
    course_ids: Iterable[int] | None = None,
    athlete_ids: Iterable[int] | None = None,
    labels: ClubLabels | None = None,
) -> None:
    """Réécrit `counts_for_tcn` sur la portée, puis `tcn_count` des épreuves touchées.

    Sans identifiant : tout. La portée d'une épreuve s'étend à tous les résultats
    de ses athlètes, la condition 3 traversant les épreuves. `course_ids` sert
    aussi à recompter une épreuve dont des lignes viennent d'être supprimées.
    `labels` : ceux d'une transaction pas encore rechargée dans le registre
    (écriture de la portée, #939) ; sinon le registre.
    """
    if labels is None:
        labels = ClubLabels.from_registry()
    courses = sorted(set(course_ids)) if course_ids is not None else None
    athletes = sorted(set(athlete_ids)) if athlete_ids is not None else None
    if courses is not None or athletes is not None:
        if not courses and not athletes:
            return
    db.flush()

    scope = _scope(courses, athletes)
    statement = update(Participation).values(
        counts_for_tcn=case((_rule(labels), True), else_=False)
    )
    if scope is not None:
        touched = set(db.scalars(select(Participation.course_id).where(scope).distinct()))
        touched.update(courses or ())
        statement = statement.where(scope)
    db.execute(statement.execution_options(synchronize_session=False))

    counted = (
        select(func.count(Participation.id))
        .where(
            Participation.course_id == Course.id,
            validated_clause(Participation.is_pending_validation),
            Participation.counts_for_tcn.is_(True),
        )
        .correlate(Course)
        .scalar_subquery()
    )
    recount = update(Course).values(tcn_count=counted)
    if scope is not None:
        recount = recount.where(Course.id.in_(sorted(touched)))
    db.execute(recount.execution_options(synchronize_session=False))
    _expire_verdicts(db)


def _expire_verdicts(db: Session) -> None:
    """Les instances déjà chargées relisent le verdict : une route qui sérialise
    une ligne qu'elle tient ne doit pas servir l'ancien."""
    for instance in list(db.identity_map.values()):
        if isinstance(instance, Participation):
            db.expire(instance, ["counts_for_tcn"])
        elif isinstance(instance, Course):
            db.expire(instance, ["tcn_count"])
```

`backend/app/repositories/course_repository.py`:
- in `recount`, replace `Course.tcn_count: _count(tcn_clause(Participation.club)),`
  with `Course.tcn_count: _count(Participation.counts_for_tcn.is_(True)),` and
  replace « Même définition que `recompute_tcn_counts_all`. » in its docstring
  with « Même définition que `tcn_count_repository.recompute_counts_for_tcn`. »;
- delete `recompute_tcn_counts_all` entirely;
- `tcn_clause` stays imported only if `_filtered`/duplicates still use it after
  Task C4 (they will not): remove the import in C4.

`backend/app/services/counter_scope.py` called the deleted function: apply
here the first bullet of Task C5 Step 3 (`_recompute_counts_for_tcn` and its
two call sites); C5 then leaves that file as it is.

Update `backend/app/models/course.py:102-116` comment: replace the sentence
about `recompute_tcn_counts_all` with « l'ajout, le retrait ou la bascule
ambiguë d'un libellé du club recalcule tout
(`tcn_count_repository.recompute_counts_for_tcn`, #939, #1206). »

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_tcn_count_repository.py tests/test_repositories/test_course_repository.py -n 0`
Expected: PASS. Then `cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_counter_scope.py tests/test_services/test_counter_scope.py -n 0`:
PASS (the counter scope service no longer calls the deleted function, see the
last bullet of Step 3).

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/repositories/tcn_count_repository.py backend/app/repositories/course_repository.py backend/app/models/course.py backend/tests/test_repositories/test_tcn_count_repository.py backend/tests/test_repositories/test_course_repository.py backend/app/services/counter_scope.py
/usr/bin/git commit -m "feat(repositories): one SQL rule recomputes counts_for_tcn and tcn_count (#1206)"
```

---

### Task C4: Repoint every counting reader to the stored verdict

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (lines 320,
  498, 845, 931, 1123, 1165, 1441; `summary_rows_for_course` selects the flag)
- Modify: `backend/app/repositories/course_repository.py` (622, 775; drop the
  `tcn_clause` import)
- Modify: `backend/app/repositories/athlete_repository.py` (736, 866, 940, 993, 1020)
- Modify: `backend/app/schemas/participation.py` (`is_tcn`)
- Modify: `backend/app/services/stats_service.py` (`course_summary`)
- Modify: `backend/app/models/participation.py` (the index comment at the top
  of `__table_args__` now lists only the `Athlete.club`-free uses: rewrite it to
  say the functional index serves `tcn_clause(Participation.club)` callers left
  in tests and the `club=` label filter, and that counting reads the indexed
  `counts_for_tcn`)
- Modify test fixture: `backend/tests/test_api/conftest.py`
  (`valider_toutes_les_participations`)
- Test: `backend/tests/test_repositories/test_counts_for_tcn_readers.py`

**Interfaces:**
- Consumes: `Participation.counts_for_tcn` (C2), `recompute_counts_for_tcn` (C3).
- Produces: `ParticipationOut.is_tcn: bool` read from `counts_for_tcn`
  (JSON key unchanged); `summary_rows_for_course` rows gain a 7th column
  `counts_for_tcn`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_repositories/test_counts_for_tcn_readers.py`:

```python
"""Every counting reader follows `counts_for_tcn`, not the bare label (#1206)."""
from datetime import date

import pytest

from app.core import counter_scope
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    tcn_count_repository,
)
from app.schemas.participation import ParticipationOut
from app.services import stats_service


@pytest.fixture
def narbonne_and_nantes(db_session):
    """Same race: a Narbonne athlete written `TCN`, a Nantes athlete written
    `TCN` whose other result says `Triathlon Club Nantais`."""
    counter_scope.load(
        disciplines=counter_scope.non_federal_disciplines(),
        club_labels=counter_scope.tcn_club_labels(),
        ambiguous_club_labels={"tcn"},
    )
    race = course_repository.get_or_create(
        db_session, name="Tri de Narbonne", event_date=date(2026, 5, 18), event_type="triathlon-m"
    )
    other = course_repository.get_or_create(
        db_session, name="Tri de Nantes", event_date=date(2026, 4, 1), event_type="triathlon-m"
    )
    narbonne = athlete_repository.get_or_create(db_session, nom="SUD", prenom="Leo")
    nantes = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    participation_repository.create(
        db_session, athlete_id=narbonne.id, course_id=race.id, bib_number="1", club="TCN",
        status="finisher", rank_overall=1,
    )
    participation_repository.create(
        db_session, athlete_id=nantes.id, course_id=race.id, bib_number="2", club="TCN",
        status="finisher", rank_overall=2,
    )
    participation_repository.create(
        db_session, athlete_id=nantes.id, course_id=other.id, bib_number="1",
        club="Triathlon Club Nantais", status="finisher", rank_overall=5,
    )
    tcn_count_repository.recompute_counts_for_tcn(db_session)
    db_session.commit()
    return race, narbonne, nantes


def test_the_club_scope_keeps_only_the_nantes_athlete(db_session, narbonne_and_nantes):
    race, _, nantes = narbonne_and_nantes

    rows = participation_repository.list_participations(
        db_session, club_only=True, page_size=100, course_id=race.id
    )

    assert [r.athlete_id for r in rows] == [nantes.id]


def test_the_course_summary_counts_one_club_result(db_session, narbonne_and_nantes):
    race, _, _ = narbonne_and_nantes

    summary = stats_service.course_summary(db_session, race.id)

    assert summary["tcn_count"] == 1
    clubs = {c["name"]: c for c in summary["clubs"]}
    assert clubs["Triathlon Club Nantais"] == {"name": "Triathlon Club Nantais", "count": 1, "is_tcn": True}
    assert clubs["TCN"] == {"name": "TCN", "count": 1, "is_tcn": False}


def test_the_events_page_and_its_fast_path_agree(db_session, narbonne_and_nantes):
    race, _, _ = narbonne_and_nantes
    db_session.expire_all()

    items = {i.id: i for i in participation_repository.events_page(db_session)["items"]}

    assert course_repository.get(db_session, race.id).tcn_count == 1
    assert items[race.id].tcn_count == 1


def test_the_badge_reads_the_stored_verdict(db_session, narbonne_and_nantes):
    race, narbonne, nantes = narbonne_and_nantes
    rows = participation_repository.list_participations(
        db_session, page_size=100, course_id=race.id
    )

    badges = {r.athlete_id: ParticipationOut.model_validate(r).is_tcn for r in rows}

    assert badges == {narbonne.id: False, nantes.id: True}
```

Before running, check the real signatures: `list_participations` keyword for
the course (`course_id` is read at line 493), `events_page` item attribute for
the course id (read `_grouped_events_query` labels around line 1150; use the
real label, e.g. `.id` or `.course_id`), and whether `events_page` groups
several courses into one event item (if it groups by event, assert on the item
of the event containing `race`). Adjust the test to the real names, keep the
assertions.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_counts_for_tcn_readers.py -n 0`
Expected: FAIL (the club scope returns both athletes; the summary counts 2).

- [ ] **Step 3: Implement**

Everywhere in the table at the top of this part (except `recount`, done in C3,
and `recompute_tcn_counts_all`, deleted), replace
`tcn_clause(Participation.club)` with `Participation.counts_for_tcn.is_(True)`.
Inside `func.sum(case((...), 1), else_=0))` keep the `case` shape:
`func.sum(case((Participation.counts_for_tcn.is_(True), 1), else_=0))`.
In `athlete_repository.club_records_with_two_bibs_on_a_race` replace
`_club_flag(Participation.club)` with
`func.max(case((Participation.counts_for_tcn.is_(True), 1), else_=0)) == 1`
(keep `_club_flag(Athlete.club)`). In `homonym_groups` line 1020 replace the
`tcn_clause(Participation.club)` only (line 1022's `Athlete.club` stays).
Remove `tcn_clause` from the imports of `participation_repository` and
`course_repository` if no use remains (`athlete_repository` keeps it).

`participation_repository.summary_rows_for_course`: add
`Participation.counts_for_tcn,` as the last selected column and append to its
docstring « La septième colonne est le verdict stocké du club (#1206). »

`backend/app/services/stats_service.py`, `course_summary`:

```python
    for status, club, category, total_time, splits, gender, counts_for_tcn in lignes:
```

then replace the club block's `if is_tcn(club):` with `if counts_for_tcn:`,
replace the trailing

```python
        if is_tcn(club):
            tcn_count += 1
```

with

```python
        if counts_for_tcn:
            tcn_count += 1
```

and in the returned `"clubs"` list replace `"is_tcn": is_tcn(nom)` with
`"is_tcn": nom == TCN_CANONICAL_NAME`. Replace the comment sentence « Le TCN
reste gouverné par `is_tcn` (registre séparé, #95) » with « Le TCN est la ligne
qui compte pour le club (`counts_for_tcn`, #1206) : un « TCN » de Narbonne reste
sur sa propre ligne ». Remove `is_tcn` from the module's `app.core.club` import
if no use remains.

`backend/app/schemas/participation.py`: remove the `is_tcn` computed field and
the `_is_tcn` import; add `AliasChoices` to the `pydantic` import; declare,
after `is_rejected`:

```python
    #: Ce résultat compte-t-il pour le club ? Verdict stocké (#1206), lu sur
    #: `Participation.counts_for_tcn` : le front n'a pas à réimplémenter la règle,
    #: c'est cette duplication qui avait laissé passer les faux positifs de #76.
    is_tcn: bool = Field(default=False, validation_alias=AliasChoices("counts_for_tcn", "is_tcn"))
```

Fix the `split_gap_ratio` docstring sentence « Exposé pour la même raison que
`is_tcn` juste au-dessus » to « Exposé pour la même raison que `is_tcn` ».

`backend/tests/test_api/conftest.py`, `valider_toutes_les_participations`:
replace `Course.tcn_count: _compte(tcn_clause(Participation.club)),` with
`Course.tcn_count: _compte(Participation.counts_for_tcn.is_(True)),`, drop the
`tcn_clause` import, and in the docstring replace `tcn_clause` with
`counts_for_tcn`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_counts_for_tcn_readers.py -n 0`
Expected: PASS. Then the whole suite: `cd backend && uv run pytest -m "not integration"`.
Expected: PASS. A failure in a test that sets a club **after** creation by a
bulk `query(...).update({"club": ...})` (listeners do not run on bulk updates)
is fixed in the test by calling
`tcn_count_repository.recompute_counts_for_tcn(db_session)` after the update;
never by reading the label again in a repository.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app backend/tests
/usr/bin/git commit -m "refactor: count club results from the stored counts_for_tcn verdict (#1206)"
```

---

### Task C5: Recompute at every write that can change a verdict

**Files:**
- Modify: `backend/app/services/import_persistence.py` (`_Persister.finalize`,
  the module created by part A; on `main` it is `import_service.py:1441-1471`)
- Modify: `backend/app/services/counter_scope.py`
- Modify: `backend/app/services/admin_actions.py` (`reassign_participation`,
  `set_teammates`, `delete_participation`, `validate_participation`,
  `update_participation_fields`)
- Modify: `backend/app/services/athlete_merge.py` (`merge_athletes`)
- Modify: `backend/app/services/opposition_service.py` (`_anonymise`)
- Modify: `backend/app/core/AGENTS.md` (paragraph « Le compteur dénormalisé »)
- Modify: `backend/app/models/AGENTS.md` (Participation bullet)
- Test: `backend/tests/test_services/test_counts_for_tcn_triggers.py`

**Interfaces:**
- Consumes: `tcn_count_repository.recompute_counts_for_tcn` (C3),
  `ClubLabels.from_entries` (C1).
- Produces: `counter_scope._recompute_counts_for_tcn(db) -> None` (private,
  reused by C6).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_services/test_counts_for_tcn_triggers.py`:

```python
"""Each write that can change a verdict recomputes it (#1206)."""
from datetime import date

import pytest

from app.core import counter_scope
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.scrapers.base import ScrapedResult
from app.services import admin_actions, athlete_merge


@pytest.fixture(autouse=True)
def _tcn_is_ambiguous():
    counter_scope.load(
        disciplines=counter_scope.non_federal_disciplines(),
        club_labels=counter_scope.tcn_club_labels(),
        ambiguous_club_labels={"tcn"},
    )


@pytest.fixture
def admin(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    return user


def _course(db, name, day):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 5, day), event_type="triathlon-m"
    )


def _result(db, athlete, course, bib, club, *, pending=False):
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=bib, club=club,
        is_pending_validation=pending,
    )


def _verdict(db, participation_id):
    db.expire_all()
    return participation_repository.get(db, participation_id).counts_for_tcn


def test_reassigning_a_bare_tcn_result_to_a_club_athlete_counts_it(db_session, admin):
    stranger = athlete_repository.get_or_create(db_session, nom="SUD", prenom="Leo")
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    bare_course = _course(db_session, "A", 1)
    bare = _result(db_session, stranger, bare_course, "1", "TCN")
    _result(db_session, member, _course(db_session, "B", 2), "1", "Triathlon Club Nantais")

    admin_actions.reassign_participation(
        db_session, participation_id=bare.id, athlete_id=member.id, user_id=admin.id
    )

    assert _verdict(db_session, bare.id) is True
    assert course_repository.get(db_session, bare_course.id).tcn_count == 1


def test_merging_athletes_counts_the_absorbed_club_result_for_the_bare_tcn(db_session, admin):
    kept = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    absorbed = athlete_repository.get_or_create(db_session, nom="OUESTE", prenom="Lea")
    bare = _result(db_session, kept, _course(db_session, "A", 1), "1", "TCN")
    _result(db_session, absorbed, _course(db_session, "B", 2), "1", "Triathlon Club Nantais")

    athlete_merge.merge_athletes(db_session, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert _verdict(db_session, bare.id) is True


def test_deleting_the_only_club_result_uncounts_the_bare_tcn(db_session, admin):
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    bare_course = _course(db_session, "A", 1)
    bare = _result(db_session, member, bare_course, "1", "TCN")
    clear_course = _course(db_session, "B", 2)
    clear = _result(db_session, member, clear_course, "1", "Triathlon Club Nantais")
    from app.repositories import tcn_count_repository

    tcn_count_repository.recompute_counts_for_tcn(db_session)
    assert _verdict(db_session, bare.id) is True

    admin_actions.delete_participation(db_session, participation_id=clear.id, user_id=admin.id)

    assert _verdict(db_session, bare.id) is False
    assert course_repository.get(db_session, bare_course.id).tcn_count == 0
    assert course_repository.get(db_session, clear_course.id).tcn_count == 0


def test_validating_a_club_result_confirms_the_bare_tcn(db_session, admin):
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    bare = _result(db_session, member, _course(db_session, "A", 1), "1", "TCN")
    clear_course = _course(db_session, "B", 2)
    pending = _result(db_session, member, clear_course, "1", "Triathlon Club Nantais", pending=True)

    admin_actions.validate_participation(db_session, participation_id=pending.id, user_id=admin.id)

    assert _verdict(db_session, bare.id) is True
    assert course_repository.get(db_session, clear_course.id).tcn_count == 1


def test_correcting_the_club_of_a_pending_result_recomputes_its_athlete(db_session, admin):
    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    bare = _result(db_session, member, _course(db_session, "A", 1), "1", "TCN", pending=True)
    _result(db_session, member, _course(db_session, "B", 2), "1", "Triathlon Club Nantais")

    admin_actions.update_participation_fields(
        db_session, participation_id=bare.id, champs={"club": "tcn "}, user_id=admin.id
    )

    assert _verdict(db_session, bare.id) is True


def test_an_import_confirms_an_older_bare_tcn_of_the_same_athlete(db_session, patch_scraper):
    from app.core.config import Settings
    from app.services import import_service

    member = athlete_repository.get_or_create(db_session, nom="OUEST", prenom="Lea")
    old_course = _course(db_session, "Ancienne", 1)
    bare = _result(db_session, member, old_course, "1", "TCN")
    db_session.commit()
    url = "https://www.klikego.com/resultats/event/456"
    patch_scraper([
        ScrapedResult(
            source_url=url, provider="klikego", athlete_name="OUEST", athlete_firstname="Lea",
            bib_number="7", club="Triathlon Club Nantais", event_name="Tri neuf",
            event_date=date(2026, 6, 1), event_type="triathlon-m", total_time="01:59:00",
        )
    ])

    import_service.import_event(
        db_session, url,
        Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000),
    )

    assert _verdict(db_session, bare.id) is True
    assert course_repository.get(db_session, old_course.id).tcn_count == 1
```

`patch_scraper` lives in `backend/tests/test_services/conftest.py` and, after
part A, patches the dispatch module: use it as it is. If
`participation_repository.get` is named differently, use the getter
`admin_actions._participation_or_404` relies on.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_services/test_counts_for_tcn_triggers.py -n 0`
Expected: FAIL on the six assertions of the verdict.

- [ ] **Step 3: Implement**

`backend/app/services/counter_scope.py` (already done in Task C3, listed here
for reference): replace `_recompute_tcn_counts` by

```python
def _recompute_counts_for_tcn(db: Session) -> None:
    """Recalcule le verdict de chaque résultat dans la transaction de l'écriture (#939, #1206).

    Les libellés sont relus **en base**, pas dans le registre : celui-ci n'est
    rechargé qu'après le commit, et le recharger avant exposerait une
    configuration que la transaction pourrait encore annuler.
    """
    entries = counter_scope_repository.list_entries(db, kind=CLUB_LABEL)
    tcn_count_repository.recompute_counts_for_tcn(
        db, labels=ClubLabels.from_entries((e.value, e.ambiguous) for e in entries)
    )
```

with `from app.core.club import ClubLabels, normalize_club` and
`from app.repositories import counter_scope_repository, tcn_count_repository`
(drop `course_repository`). In `add_entry` and `remove_entry`, replace
`_recompute_tcn_counts(db, kind)` with

```python
    if kind == CLUB_LABEL:
        _recompute_counts_for_tcn(db)
```

`_Persister.finalize` (in `import_persistence.py`), just before the
`for course_id, course in self._courses.items():` loop:

```python
        # Verdict du club avant les compteurs : `recount` le lit (#1206). La
        # portée s'étend aux autres résultats des athlètes importés.
        tcn_count_repository.recompute_counts_for_tcn(self.db, course_ids=list(self._courses))
```

(import `tcn_count_repository` from `app.repositories`.)

`backend/app/services/admin_actions.py` (import `tcn_count_repository`; drop
`from app.core.club import is_tcn`):

- `reassign_participation`: after the `delete_orphans_among` call,
  `tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=[source_id, cible.id, *anciens_equipiers], course_ids=[course_id])`.
- `set_teammates`: after its `delete_orphans_among` call,
  `tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=[source_id, *actuels, *ids], course_ids=[course_id])`.
- `delete_participation`: keep `adjust_counts` for `participation_delta=-1`
  with `tcn_delta=0`; keep `athlete_id = participation.athlete_id` and
  `course_id = participation.course_id` before the delete; after
  `participation_repository.delete(...)`:
  `tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=[athlete_id], course_ids=[course_id])`.
  Update the comment above `adjust_counts`: « le compte du club, lui, se
  recalcule après la suppression : la ligne retirée pouvait rattacher au club
  d'autres résultats de l'athlète (#1206). »
- `validate_participation`: `adjust_counts(..., participation_delta=1, tcn_delta=0)`,
  then `tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=[participation.athlete_id], course_ids=[participation.course_id])`.
- `update_participation_fields`: after the `apres == avant` early return, if
  `avant["club"] != apres["club"]`,
  `tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=[participation.athlete_id])`.

`backend/app/services/athlete_merge.py`, `merge_athletes`, after the last
`db.flush()`:
`tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=[kept.id])`
(import from `app.repositories`).

`backend/app/services/opposition_service.py`, `_anonymise`: replace
`if is_tcn(participation.club):` with `if participation.counts_for_tcn:` and
drop the `is_tcn` import. The row's club is emptied right after, which the
listener turns into `False` at the next flush.

`adjust_counts` keeps its `tcn_delta` parameter (opposition uses it).

Docs, both in French without dash punctuation:
- `backend/app/core/AGENTS.md`, replace the paragraph « **Le compteur
  dénormalisé `Course.tcn_count` ne lit pas le registre** … » with: « **Ce qui
  compte pour le club est stocké** (#1206) : `Participation.counts_for_tcn`,
  écrit par `repositories/tcn_count_repository.recompute_counts_for_tcn`, et
  `Course.tcn_count` qui en est le compte. Un libellé de la portée peut être
  **ambigu** (« tcn », aussi le Triathlon Club Narbonne) : il ne compte que si
  l'athlète est rattaché au club par un autre résultat validé. Toute écriture
  qui peut changer un verdict recalcule (import, portée, réattachement,
  équipiers, fusion, suppression, validation, correction du club) ; une
  écriture de la portée le fait à partir des libellés **relus en base**, le
  registre n'étant rechargé qu'après le commit. `is_tcn` ne dit plus que
  « libellé de la portée » et ne compte rien. »
- `backend/app/models/AGENTS.md`, Participation bullet (line ~80): add «
  `counts_for_tcn` porte le verdict du club (#1206) ; un écouteur n'en pose que
  la condition du libellé, le reste vient de `tcn_count_repository`. »

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_services/test_counts_for_tcn_triggers.py -n 0`
Expected: PASS. Then `cd backend && uv run pytest -m "not integration"`: PASS,
and `cd backend && uv run ruff check .`: clean.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app backend/tests
/usr/bin/git commit -m "feat(services): recompute the club verdict at every write that can change it (#1206)"
```

---

### Task C6: Toggle an ambiguous label from the admin API

**Files:**
- Modify: `backend/app/repositories/counter_scope_repository.py`
- Modify: `backend/app/services/counter_scope.py`
- Modify: `backend/app/schemas/counter_scope.py`
- Modify: `backend/app/api/v1/admin_counter_scope.py`
- Modify: `docs/api/admin-donnees.md` (table at line ~288)
- Test: `backend/tests/test_api/test_admin_counter_scope.py`

**Interfaces:**
- Consumes: `_recompute_counts_for_tcn` (C5).
- Produces: `counter_scope_repository.set_ambiguous(db, entry: CounterScopeEntry, ambiguous: bool) -> None`;
  service `counter_scope.set_ambiguous(db, *, entry_id: int, ambiguous: bool, user_id: int | None) -> CounterScopeEntry`;
  `CounterScopeEntryOut.ambiguous: bool`; schema `CounterScopeAmbiguityIn {ambiguous: bool}`;
  route `PATCH /admin/counter-scope/{kind}/{entry_id}` → `200` with the entry,
  `400` for a discipline, `404` for an unknown id. Audit action
  `counter_scope.entry_ambiguous`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_api/test_admin_counter_scope.py`:

```python
# --- Libellé ambigu (#1206) ---------------------------------------------------


def _entry_id(db_session, value: str) -> int:
    return counter_scope_repository.find_by_value(db_session, kind=CLUB_LABEL, value=value).id


def test_the_read_says_whether_a_label_is_ambiguous(client, db_session):
    _semer(db_session, CLUB_LABEL, "tcn")

    assert client.get(BASE).json()["club_labels"][0]["ambiguous"] is False


def test_marking_a_label_ambiguous_reloads_the_registry(client, db_session):
    _semer(db_session, CLUB_LABEL, "tcn", "tri club nantais")

    reponse = client.patch(f"{BASE}/club-labels/{_entry_id(db_session, 'tcn')}", json={"ambiguous": True})

    assert reponse.status_code == 200
    assert reponse.json()["ambiguous"] is True
    assert counter_scope.ambiguous_club_labels() == frozenset({"tcn"})


def test_an_ambiguous_label_stops_counting_a_lone_result(client, db_session, _un_resultat_au_club_inconnu):
    ajout = client.post(f"{BASE}/club-labels", json={"value": "TRIATHLON CLUB NANTAIS 44"})
    assert client.get("/api/v1/participations").json()[0]["is_tcn"] is True

    client.patch(f"{BASE}/club-labels/{ajout.json()['id']}", json={"ambiguous": True})

    assert client.get("/api/v1/participations").json()[0]["is_tcn"] is False


def test_a_discipline_cannot_be_ambiguous(client, db_session):
    _semer(db_session, NON_FEDERAL_DISCIPLINE, "trail")
    entry_id = counter_scope_repository.find_by_value(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail"
    ).id

    reponse = client.patch(f"{BASE}/disciplines/{entry_id}", json={"ambiguous": True})

    assert reponse.status_code == 400


def test_an_unknown_label_is_not_found(client):
    assert client.patch(f"{BASE}/club-labels/9999", json={"ambiguous": True}).status_code == 404


def test_the_toggle_is_logged(client, db_session):
    _semer(db_session, CLUB_LABEL, "tcn", "tri club nantais")

    client.patch(f"{BASE}/club-labels/{_entry_id(db_session, 'tcn')}", json={"ambiguous": True})

    actions = [a.action for a in db_session.query(AdminActionLog).all()]
    assert actions == ["counter_scope.entry_ambiguous"]


def test_an_unchanged_toggle_logs_nothing(client, db_session):
    _semer(db_session, CLUB_LABEL, "tcn")

    client.patch(f"{BASE}/club-labels/{_entry_id(db_session, 'tcn')}", json={"ambiguous": False})

    assert db_session.query(AdminActionLog).count() == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_counter_scope.py -n 0`
Expected: FAIL (`KeyError: 'ambiguous'`, `405 Method Not Allowed`).

- [ ] **Step 3: Implement**

`counter_scope_repository.py`:

```python
def set_ambiguous(db: Session, entry: CounterScopeEntry, ambiguous: bool) -> None:
    entry.ambiguous = ambiguous
```

`services/counter_scope.py`:

```python
def set_ambiguous(
    db: Session, *, entry_id: int, ambiguous: bool, user_id: int | None
) -> CounterScopeEntry:
    """Marque un libellé du club comme ambigu, ou le rétablit (#1206).

    Un libellé ambigu ne compte que si l'athlète est rattaché au club par
    ailleurs : le verdict de chaque résultat se recalcule dans la transaction.
    Une demande sans effet n'écrit rien au journal (FR-012).
    """
    entry = counter_scope_repository.get_entry(db, kind=CLUB_LABEL, entry_id=entry_id)
    if entry is None:
        raise NotFoundError("Cette entrée n'existe pas.")
    if entry.ambiguous == ambiguous:
        return entry
    counter_scope_repository.set_ambiguous(db, entry, ambiguous)
    db.flush()
    _recompute_counts_for_tcn(db)
    audit.record(
        db, user_id, action="counter_scope.entry_ambiguous", entity_type=_ENTITY_TYPE,
        entity_id=entry.id, payload={"ambiguous": ambiguous},
    )
    return entry
```

`schemas/counter_scope.py`: add to `CounterScopeEntryOut`

```python
    #: Libellé qui désigne aussi d'autres clubs (#1206). Toujours `False` pour
    #: une discipline.
    ambiguous: bool = False
```

and

```python
class CounterScopeAmbiguityIn(BaseModel):
    ambiguous: bool
```

`api/v1/admin_counter_scope.py`: import `DomainError` from
`app.core.exceptions` and `CounterScopeAmbiguityIn`; in `_vue` pass
`ambiguous=entry.ambiguous`; add the route

```python
@router.patch("/admin/counter-scope/{kind}/{entry_id}", response_model=CounterScopeEntryOut)
def set_counter_scope_entry_ambiguity(
    kind: ScopeKind,
    entry_id: int,
    body: CounterScopeAmbiguityIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.COUNTER_SCOPE_MANAGE)),
):
    """Marque un libellé du club comme ambigu, ou le rétablit (#1206)."""
    if kind is not ScopeKind.CLUB_LABELS:
        raise DomainError("Seul un libellé du club peut être ambigu.")
    entry = counter_scope.set_ambiguous(
        db, entry_id=entry_id, ambiguous=body.ambiguous, user_id=actor.id
    )
    db.commit()
    _recharger(db)
    db.refresh(entry)
    return _vue(entry)
```

If `_vue` reads `entry.created_by` lazily after the commit, keep the
`db.refresh(entry)`; it reloads the expired row.

`docs/api/admin-donnees.md`, after the `DELETE` row of the table:

```markdown
| `PATCH /admin/counter-scope/club-labels/{entry_id}` | `{ambiguous}` : marque un libellé du club comme ambigu, ou le rétablit (#1206). Un libellé ambigu (« tcn », aussi le Triathlon Club Narbonne) ne compte que si l'athlète est rattaché au club par un autre résultat validé ; le verdict de chaque résultat se recalcule dans la transaction. `200` avec l'entrée ; `400` sur une discipline. |
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_counter_scope.py tests/test_services/test_counter_scope.py -n 0`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/repositories/counter_scope_repository.py backend/app/services/counter_scope.py backend/app/schemas/counter_scope.py backend/app/api/v1/admin_counter_scope.py backend/tests/test_api/test_admin_counter_scope.py docs/api/admin-donnees.md
/usr/bin/git commit -m "feat(api): toggle an ambiguous club label from the counter scope admin (#1206)"
```

---

### Task C7: « Ambigu » toggle in `/admin/portee-compteurs`

**Files:**
- Modify: `frontend/lib/types.ts` (`CounterScopeEntry`)
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/queries/admin.ts`
- Modify: `frontend/components/admin/CounterScopeCard.tsx`
- Test: `frontend/components/admin/CounterScopeCard.test.tsx`

**Interfaces:**
- Consumes: `PATCH /admin/counter-scope/club-labels/{entry_id}` (C6).
- Produces: `CounterScopeEntry.ambiguous: boolean`;
  `apiClient.setCounterScopeAmbiguity(kind: ScopeKind, entryId: number, ambiguous: boolean): Promise<CounterScopeEntry>`;
  `useSetCounterScopeAmbiguity()` mutation taking `{kind, entryId, ambiguous}`.

- [ ] **Step 1: Write the failing tests**

In `frontend/components/admin/CounterScopeCard.test.tsx`: add
`setCounterScopeAmbiguity: vi.fn()` to the `vi.hoisted` object, destructure it,
add it to the mocked `apiClient`, add `ambiguous: false,` to the `entree()`
defaults, then append:

```tsx
describe("CounterScopeCard, libellés ambigus", () => {
  beforeEach(() => {
    setCounterScopeAmbiguity.mockReset();
    toastSuccess.mockReset();
    toastError.mockReset();
  });

  it("marque un libellé comme ambigu", async () => {
    setCounterScopeAmbiguity.mockResolvedValue(entree({ ambiguous: true }));
    afficher();

    await userEvent.click(screen.getByRole("checkbox", { name: "« tcn » est ambigu" }));

    expect(setCounterScopeAmbiguity).toHaveBeenCalledWith("club-labels", 1, true);
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(
        "« tcn » ne compte plus seul : il faut un autre résultat au club.",
      ),
    );
  });

  it("rétablit un libellé ambigu", async () => {
    setCounterScopeAmbiguity.mockResolvedValue(entree({ ambiguous: false }));
    afficher({ entrees: [entree({ ambiguous: true }), entree({ id: 2, value: "tri club nantais" })] });

    const caseACocher = screen.getByRole("checkbox", { name: "« tcn » est ambigu" });
    expect(caseACocher).toBeChecked();
    await userEvent.click(caseACocher);

    expect(setCounterScopeAmbiguity).toHaveBeenCalledWith("club-labels", 1, false);
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith("« tcn » compte de nouveau seul."),
    );
  });

  it("explique ce qu'est un libellé ambigu, en texte visible", () => {
    afficher();

    expect(
      screen.getByText(
        /Un libellé ambigu désigne aussi d'autres clubs/,
      ),
    ).toBeInTheDocument();
  });

  it("montre le refus du serveur", async () => {
    setCounterScopeAmbiguity.mockRejectedValue(new ApiError(403, "Accès refusé."));
    afficher();

    await userEvent.click(screen.getByRole("checkbox", { name: "« tcn » est ambigu" }));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("Accès refusé."));
  });

  it("n'offre pas la case pour une discipline", () => {
    afficher({ kind: "disciplines", entrees: [entree({ value: "trail" })], nom: "disciplines exclues" });

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
```

Check the `ApiError` constructor signature in `frontend/lib/api/client.ts`
and the existing « montre le refus du serveur » test of this file, and build
the error the same way.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npm test -- components/admin/CounterScopeCard.test.tsx`
Expected: FAIL (no checkbox).

- [ ] **Step 3: Implement**

`frontend/lib/types.ts`, in `CounterScopeEntry` after `is_known`:

```ts
  /** Libellé du club qui désigne aussi d'autres clubs (#1206) : il ne compte
   * que si l'athlète est rattaché au club par un autre résultat. Toujours
   * `false` pour une discipline. */
  ambiguous: boolean;
```

`frontend/lib/api/client.ts`, after `removeCounterScopeEntry`:

```ts
  setCounterScopeAmbiguity: (kind: ScopeKind, entryId: number, ambiguous: boolean) =>
    request<CounterScopeEntry>(`/admin/counter-scope/${kind}/${entryId}`, {
      method: "PATCH",
      body: JSON.stringify({ ambiguous }),
    }),
```

`frontend/lib/queries/admin.ts`, after `useRemoveCounterScopeEntry`:

```ts
export function useSetCounterScopeAmbiguity() {
  const toutPerimer = useInvalidationDeLaPorteeDesCompteurs();
  return useMutation({
    mutationFn: ({
      kind,
      entryId,
      ambiguous,
    }: {
      kind: ScopeKind;
      entryId: number;
      ambiguous: boolean;
    }) => apiClient.setCounterScopeAmbiguity(kind, entryId, ambiguous),
    onSuccess: toutPerimer,
  });
}
```

`frontend/components/admin/CounterScopeCard.tsx`:
- import `useSetCounterScopeAmbiguity`; `const basculer = useSetCounterScopeAmbiguity();`
- add

```tsx
  async function basculerAmbiguite(entree: CounterScopeEntry, ambiguous: boolean) {
    try {
      await basculer.mutateAsync({ kind, entryId: entree.id, ambiguous });
      toast.success(
        ambiguous
          ? `« ${entree.value} » ne compte plus seul : il faut un autre résultat au club.`
          : `« ${entree.value} » compte de nouveau seul.`,
      );
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
```

- in the club label branch of each `<li>` (the `<span className="font-mono text-sm">`
  case), right after the value span:

```tsx
                  {kind === "club-labels" && (
                    // Case native et `<label>` englobant : cible de 24 px au
                    // moins, nom accessible lu tel quel par les aides techniques.
                    <label className="flex min-h-6 items-center gap-2 text-xs text-muted-foreground">
                      <input
                        type="checkbox"
                        className="size-4 accent-[var(--tcn-primary)]"
                        checked={entree.ambiguous}
                        disabled={basculer.isPending}
                        onChange={(e) => basculerAmbiguite(entree, e.target.checked)}
                        aria-label={`« ${entree.value} » est ambigu`}
                      />
                      Ambigu
                    </label>
                  )}
```

  (check that `--tcn-primary` exists in `frontend/app/globals.css`; otherwise
  use the token the other admin forms use for an accent);
- after the `uneDisciplineInconnue` paragraph, inside the same fragment:

```tsx
            {kind === "club-labels" && (
              <p className="text-xs text-[var(--tcn-text-faint)]">
                Un libellé ambigu désigne aussi d&apos;autres clubs (« TCN » est aussi le
                Triathlon Club Narbonne). Un résultat qui ne porte que lui compte pour le
                club seulement si l&apos;athlète a un autre résultat validé sous un libellé
                non ambigu.
              </p>
            )}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npm test -- components/admin/CounterScopeCard.test.tsx app/admin/portee-compteurs`
Expected: PASS. Then `cd frontend && npm run lint && npx tsc --noEmit`: clean
(every `CounterScopeEntry` literal in other test files needs `ambiguous`;
`tsc` lists them).

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add frontend/lib/types.ts frontend/lib/api/client.ts frontend/lib/queries/admin.ts frontend/components/admin/CounterScopeCard.tsx frontend/components/admin/CounterScopeCard.test.tsx
/usr/bin/git commit -m "feat(frontend): mark a club label as ambiguous in the counter scope screen (#1206)"
```


# Partie D

## Part D: Club members per season (#1202) and RGPD

Runs after part C. Part C delivered:

- `Participation.counts_for_tcn` (stored bool);
- `CounterScopeEntry.ambiguous`;
- `backend/app/repositories/tcn_count_repository.py`, with
  `recompute_counts_for_tcn(db, *, course_ids=None, athlete_ids=None)`. Called
  with no filter, it recomputes every participation and then
  `Course.tcn_count`. It is built on a private expression builder that today
  implements conditions 1 (unambiguous label in scope) and 3 (ambiguous label
  confirmed by another unambiguous result of the athlete).

Part D adds the member list, condition 2, the licence branch of condition 3,
and the screens and legal texts around them.

Decisions taken in this part (measured on the real page, 2026-10-06):

- **Licence year.** The JSON-LD `SportsTeam` block lists the members but not
  the year. The year is read from the visible text « Membre · 2027 », present
  once per member card. Exactly one distinct year is required, otherwise the
  page is unreadable.
- **Name split.** `name` is « NOM Prénom ». The last name is the leading run of
  fully upper-case words, the first name is the rest.
  - « BELBEOC H Victor » → (« BELBEOC H », « Victor »).
  - « BOURGAIN  VIALAR Albane » → (« BOURGAIN VIALAR », « Albane »).
  - « ABOT Anne sophie » → (« ABOT », « Anne sophie »).
  - The identity key ignores spaces, so « BELBEOC H » matches « BELBEOC'H ».
- **Gender.** `Female` → `F`, `Male` → `M`, anything else → `""`.
- **Season mapping.** Licence year Y → `season = Y - 1` (the « 2027 » licence
  read in October 2026 covers September 2026 to August 2027).
- **Fixture data.** The test fixture keeps the real page structure but uses
  fictitious names and licence numbers. Real member names never enter the
  repository.
- **Retention.** Seasons older than `current_season() - 1` are purged as
  follows:
  - unlinked and ambiguous rows are deleted;
  - linked rows keep only `(season, athlete_id, link_status, source)`:
    `licence_id` is cleared and `nom`/`prenom` are replaced by the linked
    record's own name.
  This keeps `counts_for_tcn` of past seasons stable without keeping a second
  copy of the licence data. The decision doc addendum (D9) states it.
- **Upload helper.** `_lire_borne` and `FileTooLargeError` move from
  `api/v1/admin_batches.py` to a shared `app/api/uploads.py`
  (`read_bounded_upload`), used by both routers. No re-export.

---

### Task D1: FFTri roster parser

**Files:**
- Create: `backend/app/scrapers/fftri_club_members.py`
- Create: `backend/tests/fixtures/fftri_club_members.html` (generated in Step 1)
- Test: `backend/tests/test_fftri_club_members.py`

**Interfaces:**
- Produces:
  - `CLUB_URL: str`
  - `@dataclass(frozen=True) RosterMember(nom: str, prenom: str, gender: str, licence_id: str | None)`
  - `@dataclass(frozen=True) ClubRoster(licence_year: int, members: list[RosterMember])`
  - `class RosterUnreadableError(Exception)`
  - `split_name(full: str) -> tuple[str, str]`
  - `parse_club_roster(html: str) -> ClubRoster`
  - `fetch_club_roster(url: str) -> ClubRoster`

- [ ] **Step 1: Generate the trimmed, anonymised fixture**

Run from `backend/`. The snippet copies the shape of the first real JSON-LD
member, so the fixture keeps every key the page publishes, and substitutes
fictitious identities:

```bash
uv run python - <<'EOF'
import json, re, pathlib
src = pathlib.Path("/tmp/claude-1000/-home-mherrmann-Documents-work-tcn-data-triathlon--claude-worktrees-backlog-batch-2026-10-06/088b5b3c-0c30-4b03-8331-26c15a3cd049/scratchpad/t2/club.html").read_text(encoding="utf-8")
blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S)
team = next(json.loads(b) for b in blocks if '"SportsTeam"' in b)
shape = team["member"][0]
people = [
    ("MARTIN Anne sophie", "Female", "C00001"),
    ("KERBRAT H Victor", "Male", "C00002"),
    ("DURAND  VIALAR Albane", "Female", "C00003"),
    ("LE GOFF Loan", "Male", "C00004"),
]
team["member"] = [
    {**shape, "name": name, "gender": gender, "identifier": ident,
     "alternateName": ident.lower(), "url": f"/athletes/{ident.lower()}.html",
     "image": "/images/usernoavatar.webp"}
    for name, gender, ident in people
]
team["description"] = "Fixture anonymisée (#1202)."
cards = "\n".join(
    f'<div class="member"><span>{name}</span><span>Membre&nbsp;·&nbsp;2027</span></div>'
    for name, _, _ in people
)
html = (
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    f'<script type="application/ld+json">{json.dumps(team, ensure_ascii=False)}</script>'
    '<script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[]}</script>'
    f"</head><body><h1>TRIATHLON CLUB NANTAIS</h1><a>Saison 2026</a><a>Saison 2027</a>{cards}</body></html>\n"
)
pathlib.Path("tests/fixtures/fftri_club_members.html").write_text(html, encoding="utf-8")
EOF
```

Check that `grep -c 'Membre' tests/fixtures/fftri_club_members.html` prints `1`
(one line, four cards) and that no real name from the source page appears.

- [ ] **Step 2: Write the failing tests**

```python
"""Liste des licenciés publiée par la FFTri sur T2Area (#1202)."""
from pathlib import Path

import httpx
import pytest

from app.scrapers import fftri_club_members
from app.scrapers.fftri_club_members import (
    CLUB_URL,
    RosterMember,
    RosterUnreadableError,
    parse_club_roster,
    split_name,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fftri_club_members.html"


def test_parse_reads_the_licence_year_and_every_member():
    roster = parse_club_roster(FIXTURE.read_text(encoding="utf-8"))

    assert roster.licence_year == 2027
    assert roster.members == [
        RosterMember("MARTIN", "Anne sophie", "F", "C00001"),
        RosterMember("KERBRAT H", "Victor", "M", "C00002"),
        RosterMember("DURAND VIALAR", "Albane", "F", "C00003"),
        RosterMember("LE GOFF", "Loan", "M", "C00004"),
    ]


@pytest.mark.parametrize(
    ("full", "expected"),
    [
        ("ABOT Anne sophie", ("ABOT", "Anne sophie")),
        ("BELBEOC H Victor", ("BELBEOC H", "Victor")),
        ("BOURGAIN  VIALAR Albane", ("BOURGAIN VIALAR", "Albane")),
        ("L AOT Sebastien", ("L AOT", "Sebastien")),
        ("DUPONT JEAN", ("DUPONT", "JEAN")),
        ("Inconnu", ("Inconnu", "")),
        ("", ("", "")),
    ],
)
def test_split_name_takes_the_leading_upper_case_run_as_last_name(full, expected):
    assert split_name(full) == expected


def test_a_page_without_the_json_ld_team_is_unreadable():
    with pytest.raises(RosterUnreadableError):
        parse_club_roster("<html><body>Membre · 2027</body></html>")


def test_a_page_without_licence_year_is_unreadable():
    html = FIXTURE.read_text(encoding="utf-8").replace("2027", "")
    with pytest.raises(RosterUnreadableError):
        parse_club_roster(html)


def test_a_page_with_two_licence_years_is_unreadable():
    html = FIXTURE.read_text(encoding="utf-8").replace("</body>", "<span>Membre · 2026</span></body>")
    with pytest.raises(RosterUnreadableError):
        parse_club_roster(html)


def test_an_empty_roster_is_unreadable_rather_than_an_empty_season():
    # La synchro ne doit jamais vider une saison.
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@type": "SportsTeam", "member": []}</script></head>'
        "<body><span>Membre · 2027</span></body></html>"
    )
    with pytest.raises(RosterUnreadableError):
        parse_club_roster(html)


def test_fetch_reads_the_page_through_the_app_http_client(monkeypatch):
    html = FIXTURE.read_text(encoding="utf-8")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=html)

    monkeypatch.setattr(
        fftri_club_members.http, "client",
        lambda **_: httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert fftri_club_members.fetch_club_roster(CLUB_URL).licence_year == 2027
    assert seen == [CLUB_URL]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_fftri_club_members.py -n 0 -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.scrapers.fftri_club_members'`.

- [ ] **Step 4: Implement**

```python
"""Licenciés du club publiés par la FFTri sur T2Area (#1202).

La page club porte un bloc JSON-LD `SportsTeam` dont `member[]` liste les
licenciés de la saison en cours : `name` « NOM Prénom », `gender`
(`Female`/`Male`), `identifier` (numéro de licence). L'année de licence n'y
figure pas : elle se lit sur chaque carte, « Membre · 2027 ».

Ce n'est pas un fournisseur de résultats : le module n'est pas inscrit au
registre et n'expose pas `scrape_event_all`.
"""
import json
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from app.core import http

from .utils import DEFAULT_HEADERS

CLUB_URL = "https://fftri.t2area.com/clubs/triathlon-club-nantais.html"

_LICENCE_YEAR = re.compile(r"Membre\s*·\s*(\d{4})")
_GENDERS = {"Female": "F", "Male": "M"}


@dataclass(frozen=True)
class RosterMember:
    nom: str
    prenom: str
    gender: str
    licence_id: str | None


@dataclass(frozen=True)
class ClubRoster:
    licence_year: int
    members: list[RosterMember]


class RosterUnreadableError(Exception):
    """La page ne se lit plus comme mesuré le 2026-10-06."""


def split_name(full: str) -> tuple[str, str]:
    """Le nom est la suite de mots en capitales qui ouvre le libellé, le prénom le reste.

    « BELBEOC H Victor » garde « BELBEOC H » : la clé d'identité ignore
    l'espace et rejoint « BELBEOC'H » des classements. Le dernier mot reste
    toujours au prénom, même en capitales (« DUPONT JEAN »).
    """
    words = full.split()
    cut = 0
    while cut < len(words) - 1 and words[cut].isupper():
        cut += 1
    if cut == 0:
        return " ".join(words), ""
    return " ".join(words[:cut]), " ".join(words[cut:])


def _team(soup: BeautifulSoup) -> dict:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "SportsTeam":
            return data
    raise RosterUnreadableError("bloc JSON-LD SportsTeam introuvable")


def parse_club_roster(html: str) -> ClubRoster:
    soup = BeautifulSoup(html, "lxml")
    team = _team(soup)
    years = {int(year) for year in _LICENCE_YEAR.findall(soup.get_text(" "))}
    if len(years) != 1:
        raise RosterUnreadableError(f"année de licence illisible : {sorted(years)}")
    members = []
    for person in team.get("member") or []:
        nom, prenom = split_name(person.get("name") or "")
        if not nom:
            continue
        members.append(RosterMember(
            nom=nom,
            prenom=prenom,
            gender=_GENDERS.get(person.get("gender"), ""),
            licence_id=(person.get("identifier") or "").strip() or None,
        ))
    # Une liste vide viderait la saison à la synchro : refusée comme illisible.
    if not members:
        raise RosterUnreadableError("aucun licencié lu")
    return ClubRoster(licence_year=years.pop(), members=members)


def fetch_club_roster(url: str) -> ClubRoster:
    with http.client(timeout=30, headers=DEFAULT_HEADERS) as client:
        response = client.get(url)
        response.raise_for_status()
    return parse_club_roster(response.text)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_fftri_club_members.py tests/test_layering.py tests/test_core_http.py -n 0 -q`
Expected: PASS. `test_core_http.py` holds the meta-test against bare `httpx`.

- [ ] **Step 6: Commit**

```bash
/usr/bin/git add backend/app/scrapers/fftri_club_members.py backend/tests/fixtures/fftri_club_members.html backend/tests/test_fftri_club_members.py
/usr/bin/git commit -m "feat(members): parse the FFTri club roster page (#1202)"
```

---

### Task D2: `ClubMember` model, migration, repository

**Files:**
- Create: `backend/app/models/club_member.py`
- Modify: `backend/app/models/__init__.py`, which imports and lists
  `ClubMember` in `__all__`
- Modify: `backend/app/models/AGENTS.md`, which gets a `ClubMember` entry
  (table, season convention, link statuses, retention rule)
- Create: `backend/alembic/versions/<new>_club_members.py`
- Create: `backend/app/repositories/club_member_repository.py`
- Modify: `backend/app/repositories/athlete_repository.py`, adding
  `get_all_ranks_by_identity_keys`
- Test: `backend/tests/test_repositories/test_club_member_repository.py`,
  `backend/tests/test_repositories/test_athlete_repository.py`,
  `backend/tests/test_migrations.py`

**Interfaces:**
- Consumes: `athlete_identity_keys` (`app/core/athlete_identity.py`).
- Produces:
  - constants `LINK_AUTO = "auto"`, `LINK_MANUAL = "manual"`,
    `LINK_UNLINKED = "unlinked"`, `LINK_AMBIGUOUS = "ambiguous"`,
    `LINKED = (LINK_AUTO, LINK_MANUAL)`, `SOURCE_FFTRI = "fftri"`,
    `SOURCE_FILE = "file"`, all in `app.models.club_member`.
  - `ClubMember` (columns `id`, `season`, `licence_id`, `nom`, `prenom`,
    `gender`, `last_name_key`, `first_name_key`, `athlete_id`, `link_status`,
    `source`, `created_at`).
  - `athlete_repository.get_all_ranks_by_identity_keys(db, keys) -> dict[IdentityKey, list[Athlete]]`
  - `club_member_repository`:
    - `list_season(db, season: int) -> list[ClubMember]` (ordered by `nom`, `prenom`)
    - `seasons(db) -> list[int]` (descending)
    - `get(db, member_id: int) -> ClubMember | None`
    - `replace_season(db, season: int, members: list[ClubMember]) -> None`
    - `purge_before(db, season: int, *, dry_run: bool) -> int`, where rows
      with `season < season` are handled as described in the header

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_repositories/test_club_member_repository.py`:

```python
"""Licenciés du club par saison (#1202)."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.athlete import Athlete
from app.models.club_member import LINK_AUTO, LINK_UNLINKED, SOURCE_FFTRI, ClubMember
from app.repositories import club_member_repository


def _member(season=2026, nom="MARTIN", prenom="Anne", licence_id="C1", **fields) -> ClubMember:
    return ClubMember(
        season=season, nom=nom, prenom=prenom, licence_id=licence_id,
        gender=fields.pop("gender", "F"), link_status=fields.pop("link_status", LINK_UNLINKED),
        source=fields.pop("source", SOURCE_FFTRI), **fields,
    )


def test_identity_keys_are_stored_on_insert(db_session):
    club_member_repository.replace_season(db_session, 2026, [_member(nom="LE GOFF", prenom="Loan")])

    (row,) = club_member_repository.list_season(db_session, 2026)
    assert (row.last_name_key, row.first_name_key) == ("legoff", "loan")


def test_replace_season_leaves_other_seasons_alone(db_session):
    club_member_repository.replace_season(db_session, 2025, [_member(season=2025)])
    club_member_repository.replace_season(db_session, 2026, [_member(licence_id="C2")])

    club_member_repository.replace_season(db_session, 2026, [_member(nom="DURAND", licence_id="C3")])

    assert [m.licence_id for m in club_member_repository.list_season(db_session, 2025)] == ["C1"]
    assert [m.licence_id for m in club_member_repository.list_season(db_session, 2026)] == ["C3"]
    assert club_member_repository.seasons(db_session) == [2026, 2025]


def test_a_licence_appears_once_per_season(db_session):
    db_session.add_all([_member(), _member(nom="AUTRE")])
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_without_licence_a_name_appears_once_per_season(db_session):
    db_session.add_all([_member(licence_id=None), _member(licence_id=None)])
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_two_homonyms_with_distinct_licences_coexist(db_session):
    db_session.add_all([_member(licence_id="C1"), _member(licence_id="C2")])
    db_session.flush()


def test_purge_deletes_unlinked_rows_and_strips_linked_ones(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.flush()
    club_member_repository.replace_season(db_session, 2024, [
        _member(season=2024, licence_id="C1", athlete_id=athlete.id, link_status=LINK_AUTO,
                nom="MARTIN", prenom="Anne"),
        _member(season=2024, licence_id="C2", nom="INCONNU", prenom="Paul"),
    ])
    club_member_repository.replace_season(db_session, 2025, [_member(season=2025, licence_id="C9")])

    assert club_member_repository.purge_before(db_session, 2025, dry_run=True) == 2
    assert len(club_member_repository.list_season(db_session, 2024)) == 2

    assert club_member_repository.purge_before(db_session, 2025, dry_run=False) == 2
    (kept,) = club_member_repository.list_season(db_session, 2024)
    assert (kept.athlete_id, kept.licence_id) == (athlete.id, None)
    assert [m.licence_id for m in club_member_repository.list_season(db_session, 2025)] == ["C9"]
```

Append to `backend/tests/test_repositories/test_athlete_repository.py`:

```python
def test_get_all_ranks_by_identity_keys_returns_homonyms_too(db_session):
    principal = Athlete(nom="MARTIN", prenom="Anne")
    homonym = Athlete(nom="Martin", prenom="Anne", homonym_rank=1)
    other = Athlete(nom="DURAND", prenom="Paul")
    db_session.add_all([principal, homonym, other])
    db_session.flush()

    found = athlete_repository.get_all_ranks_by_identity_keys(
        db_session, [("martin", "anne"), ("absent", "x"), (None, None)]
    )

    assert sorted(a.id for a in found[("martin", "anne")]) == sorted([principal.id, homonym.id])
    assert ("absent", "x") not in found
```

Append to `backend/tests/test_migrations.py`:

```python
def test_club_members_table_is_created(base_migree):
    assert _columns(base_migree, "club_members") == {
        "id", "season", "licence_id", "nom", "prenom", "gender", "last_name_key",
        "first_name_key", "athlete_id", "link_status", "source", "created_at",
    }


def test_downgrade_then_upgrade_of_club_members(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "<PREVIOUS_HEAD>")
    assert "club_members" not in _tables(sqlite_url)
    command.upgrade(cfg, "head")
    assert "club_members" in _tables(sqlite_url)
```

`<PREVIOUS_HEAD>` is the head left by part C. Read it with
`cd backend && uv run alembic heads` before creating the migration, and write it
literally (a named target, per the file's own convention).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_repositories/test_club_member_repository.py tests/test_repositories/test_athlete_repository.py -k "club_member or all_ranks" -n 0 -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.models.club_member'`.

- [ ] **Step 3: Implement the model**

`backend/app/models/club_member.py`:

```python
"""ClubMember : un licencié du club pour une saison (#1202).

Lu sur la page FFTri du club ou importé d'un fichier pour une saison passée.
`season` suit `core/season` (année de début) : la licence FFTri « 2027 »,
publiée dès septembre 2026, couvre la saison 2026.

Rattaché à une fiche, il fait compter pour le club les résultats de cette
fiche sur la saison (`tcn_count_repository`). Les clés d'identité sont écrites
par l'écouteur, comme celles d'`Athlete`.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, event, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.athlete_identity import athlete_identity_keys
from app.core.database import Base
from app.core.time import utcnow

LINK_AUTO = "auto"
LINK_MANUAL = "manual"
LINK_UNLINKED = "unlinked"
LINK_AMBIGUOUS = "ambiguous"
LINKED = (LINK_AUTO, LINK_MANUAL)

SOURCE_FFTRI = "fftri"
SOURCE_FILE = "file"


class ClubMember(Base):
    __tablename__ = "club_members"
    __table_args__ = (
        UniqueConstraint("season", "licence_id", name="uq_club_member_licence"),
        # Sans numéro de licence (fichier importé), le nom seul identifie : deux
        # homonymes y sont indiscernables. Avec un numéro, ils coexistent.
        Index(
            "uq_club_member_identity_without_licence",
            "season", "last_name_key", "first_name_key",
            unique=True,
            postgresql_where=text("licence_id IS NULL"),
            sqlite_where=text("licence_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    licence_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nom: Mapped[str] = mapped_column(String)
    prenom: Mapped[str] = mapped_column(String, default="")
    gender: Mapped[str] = mapped_column(String(1), default="")
    last_name_key: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name_key: Mapped[str | None] = mapped_column(String, nullable=True)
    athlete_id: Mapped[int | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    link_status: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


@event.listens_for(ClubMember, "before_insert")
@event.listens_for(ClubMember, "before_update")
def _store_identity_keys(_mapper, _connection, member: ClubMember) -> None:
    member.last_name_key, member.first_name_key = athlete_identity_keys(member.nom, member.prenom)
```

Register in `backend/app/models/__init__.py`: add
`from app.models.club_member import ClubMember` (alphabetical, after
`club_alias`) and `"ClubMember"` in `__all__`.

- [ ] **Step 4: Generate and edit the migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "club members"
```

Rename the generated file to `<rev>_club_members.py`. Check:
- the docstring says « Licenciés du club par saison (#1202) » and explains the
  partial unique index;
- `down_revision` is the head left by part C;
- `upgrade` creates the table, `ix_club_members_season`,
  `ix_club_members_athlete_id`, the `uq_club_member_licence` constraint, and the
  partial index with both `postgresql_where=sa.text("licence_id IS NULL")` and
  `sqlite_where=sa.text("licence_id IS NULL")` (autogenerate drops
  `sqlite_where`, so add it by hand);
- `downgrade` drops the indexes and then the table;
- `__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]`
  is present, as in the other migrations.

- [ ] **Step 5: Implement the repositories**

Append to `backend/app/repositories/athlete_repository.py`, after
`get_by_identity_keys_batch`:

```python
def get_all_ranks_by_identity_keys(
    db: Session, keys: Sequence[IdentityKey]
) -> dict[IdentityKey, list[Athlete]]:
    """Toutes les fiches de ces clés, homonymes distingués compris (#1202).

    Le rattachement d'un licencié doit voir les homonymes : deux fiches pour
    une clé, c'est un rattachement ambigu, que seul un humain tranche.
    """
    wanted = {key for key in keys if key[0] is not None}
    if not wanted:
        return {}
    found: dict[IdentityKey, list[Athlete]] = {}
    for athlete in db.scalars(
        select(Athlete)
        .where(tuple_(Athlete.last_name_key, Athlete.first_name_key).in_(wanted))
        .order_by(Athlete.homonym_rank)
    ):
        found.setdefault((athlete.last_name_key, athlete.first_name_key), []).append(athlete)
    return found
```

`backend/app/repositories/club_member_repository.py`:

```python
"""Accès données des licenciés du club par saison (#1202)."""
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.models.athlete import Athlete
from app.models.club_member import LINKED, ClubMember


def list_season(db: Session, season: int) -> list[ClubMember]:
    return list(db.scalars(
        select(ClubMember).where(ClubMember.season == season).order_by(ClubMember.nom, ClubMember.prenom)
    ))


def seasons(db: Session) -> list[int]:
    return list(db.scalars(select(ClubMember.season).distinct().order_by(ClubMember.season.desc())))


def get(db: Session, member_id: int) -> ClubMember | None:
    return db.get(ClubMember, member_id)


def replace_season(db: Session, season: int, members: list[ClubMember]) -> None:
    """Remplace toute la liste d'une saison, en une transaction."""
    db.execute(delete(ClubMember).where(ClubMember.season == season))
    db.flush()
    db.add_all(members)
    db.flush()


def purge_before(db: Session, season: int, *, dry_run: bool) -> int:
    """Tient la durée de conservation (#1202) : rend le nombre de lignes touchées.

    Une ligne non rattachée disparaît. Une ligne rattachée ne garde que le fait
    « cette fiche était licenciée cette saison », qui fait compter ses
    résultats d'alors : numéro de licence effacé, nom et prénom remplacés par
    ceux de la fiche.
    """
    old = ClubMember.season < season
    pending = or_(ClubMember.licence_id.is_not(None), ClubMember.link_status.not_in(LINKED))
    touched = db.scalar(select(func.count()).select_from(ClubMember).where(old, pending))
    if dry_run:
        return touched
    db.execute(delete(ClubMember).where(old, ClubMember.link_status.not_in(LINKED)))
    db.execute(
        update(ClubMember)
        .where(old, ClubMember.link_status.in_(LINKED))
        .values(
            licence_id=None,
            nom=select(Athlete.nom).where(Athlete.id == ClubMember.athlete_id).scalar_subquery(),
            prenom=select(Athlete.prenom).where(Athlete.id == ClubMember.athlete_id).scalar_subquery(),
        )
        .execution_options(synchronize_session=False)
    )
    db.flush()
    return touched
```

Caveat on `purge_before`: the bulk `update` bypasses the `before_update`
listener, so the keys keep the old values. That is acceptable because the
names written come from the linked record, whose keys are the same unless the
record was renamed. The test above only checks `athlete_id` and `licence_id`.

`touched` counts a linked row only if its licence was not cleared yet. A second
run therefore counts only what is left to purge, which keeps a weekly dry run
honest.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_repositories/test_club_member_repository.py tests/test_repositories/test_athlete_repository.py tests/test_migrations.py tests/test_layering.py -n 0 -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
/usr/bin/git add backend/app/models/club_member.py backend/app/models/__init__.py backend/app/models/AGENTS.md backend/alembic/versions backend/app/repositories/club_member_repository.py backend/app/repositories/athlete_repository.py backend/tests/test_repositories/test_club_member_repository.py backend/tests/test_repositories/test_athlete_repository.py backend/tests/test_migrations.py
/usr/bin/git commit -m "feat(members): store club members per season (#1202)"
```

---

### Task D3: Condition 2 and the licence branch of condition 3

**Files:**
- Modify: `backend/app/repositories/tcn_count_repository.py`
- Test: `backend/tests/test_repositories/test_tcn_count_repository.py` (the test
  file created by part C; append)

**Interfaces:**
- Consumes:
  - `ClubMember`, `LINKED` (D2);
  - `ParticipationTeammate` (`app.models.participation`);
  - the part C private builder of the `counts_for_tcn` expression. Read the
    file first. The builder returns `or_(<condition 1>, <condition 3>)`, and
    condition 3 is `and_(<label is ambiguous in scope>, <athlete confirmed>)`,
    where `<athlete confirmed>` is today an `exists()` over another unambiguous
    result.
- Produces: the same `recompute_counts_for_tcn` signature, with the rule now
  complete.

- [ ] **Step 1: Write the failing tests**

Reuse the helpers part C put at the top of the test file (`_athlete`, `_course`,
`_result`, a scope seeding helper). If one is missing, define it like this:

```python
from datetime import date

from app.models.athlete import Athlete
from app.models.club_member import LINK_AUTO, LINK_UNLINKED, SOURCE_FFTRI, ClubMember
from app.models.counter_scope_entry import CLUB_LABEL, CounterScopeEntry
from app.models.participation import Participation
from app.repositories import course_repository, participation_repository, tcn_count_repository


def _athlete(db, nom="MARTIN", prenom="Anne"):
    athlete = Athlete(nom=nom, prenom=prenom)
    db.add(athlete)
    db.flush()
    return athlete


def _course(db, event_date=date(2026, 10, 10), name="Tri A", is_relay=False):
    return course_repository.get_or_create(
        db, name=name, event_date=event_date, event_type="triathlon-m", is_relay=is_relay
    )


def _result(db, athlete, course, bib="1", club=None, **fields):
    return participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=bib,
        status="finisher", club=club, **fields,
    )


def _licence(db, athlete, season, link_status=LINK_AUTO):
    db.add(ClubMember(
        season=season, nom=athlete.nom, prenom=athlete.prenom, licence_id=f"C{athlete.id}-{season}",
        athlete_id=athlete.id, link_status=link_status, source=SOURCE_FFTRI,
    ))
    db.flush()


def _counts(db, participation) -> bool:
    db.refresh(participation)
    return participation.counts_for_tcn
```

Tests to append:

```python
def test_a_member_of_the_course_season_counts_without_club_label(db_session):
    athlete = _athlete(db_session)
    result = _result(db_session, athlete, _course(db_session, event_date=date(2026, 10, 10)))
    _licence(db_session, athlete, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert _counts(db_session, result)


def test_a_licence_of_another_season_does_not_count(db_session):
    athlete = _athlete(db_session)
    # Le 31 août 2026 appartient à la saison 2025 : la licence 2026 ne la couvre pas.
    result = _result(db_session, athlete, _course(db_session, event_date=date(2026, 8, 31)))
    _licence(db_session, athlete, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert not _counts(db_session, result)


def test_an_unlinked_member_row_does_not_count(db_session):
    athlete = _athlete(db_session)
    result = _result(db_session, athlete, _course(db_session))
    _licence(db_session, athlete, season=2026, link_status=LINK_UNLINKED)

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert not _counts(db_session, result)


def test_a_relay_counts_when_a_teammate_is_a_member(db_session):
    team = _athlete(db_session, nom="EQUIPE", prenom="Bleue")
    teammate = _athlete(db_session, nom="DURAND", prenom="Paul")
    result = participation_repository.create_batch(db_session, [{
        "athlete_id": team.id, "course_id": _course(db_session, is_relay=True).id,
        "bib_number": "7", "status": "finisher", "teammate_ids": [teammate.id],
    }])[0]
    _licence(db_session, teammate, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert _counts(db_session, result)


def test_an_ambiguous_label_counts_for_a_licensed_athlete_of_any_season(db_session):
    db_session.add(CounterScopeEntry(kind=CLUB_LABEL, value="tcn", ambiguous=True))
    athlete = _athlete(db_session)
    result = _result(db_session, athlete, _course(db_session), club="TCN")
    _licence(db_session, athlete, season=2019)

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert _counts(db_session, result)


def test_an_ambiguous_label_alone_does_not_count(db_session):
    db_session.add(CounterScopeEntry(kind=CLUB_LABEL, value="tcn", ambiguous=True))
    result = _result(db_session, _athlete(db_session), _course(db_session), club="TCN")

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    assert not _counts(db_session, result)


def test_the_course_counter_follows_membership(db_session):
    athlete = _athlete(db_session)
    course = _course(db_session)
    _result(db_session, athlete, course)
    _licence(db_session, athlete, season=2026)

    tcn_count_repository.recompute_counts_for_tcn(db_session)

    db_session.refresh(course)
    assert course.tcn_count == 1
```

Check `create_batch`'s `teammate_ids` key against its docstring; if the relay
participation also needs `is_relay=True`, pass it. If part C's recompute only
counts validated participations, the `status="finisher"` default rows above are
validated by default (`is_pending_validation` defaults to false).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_repositories/test_tcn_count_repository.py -n 0 -q`
Expected: the four membership tests FAIL (`assert False`), the two others PASS.

- [ ] **Step 3: Implement**

Add to `tcn_count_repository.py`, next to the builder:

```python
from sqlalchemy import case, exists, extract, or_, select

from app.models.club_member import LINKED, ClubMember
from app.models.course import Course
from app.models.participation import Participation, ParticipationTeammate


def _course_season():
    """Saison (année de début) de l'épreuve du résultat, miroir SQL de `season_of`.

    Une épreuve sans date n'a pas de saison : la comparaison rend NULL, donc
    faux, et aucune licence ne la couvre.
    """
    event_date = (
        select(Course.event_date)
        .where(Course.id == Participation.course_id)
        .correlate(Participation)
        .scalar_subquery()
    )
    year = extract("year", event_date)
    return case((extract("month", event_date) >= 9, year), else_=year - 1)


def _licensed(athlete_id_column, season=None):
    clauses = [ClubMember.athlete_id == athlete_id_column, ClubMember.link_status.in_(LINKED)]
    if season is not None:
        clauses.append(ClubMember.season == season)
    return exists().where(*clauses)


def _member_of_course_season():
    """Condition 2 : l'athlète, ou un équipier du relais, est licencié la saison de l'épreuve (#1202)."""
    season = _course_season()
    teammate = (
        select(ParticipationTeammate.athlete_id)
        .where(ParticipationTeammate.participation_id == Participation.id)
        .correlate(Participation)
    )
    return or_(
        _licensed(Participation.athlete_id, season),
        exists().where(
            ClubMember.athlete_id.in_(teammate),
            ClubMember.link_status.in_(LINKED),
            ClubMember.season == season,
        ),
    )
```

Then edit the builder:

1. Add `_member_of_course_season()` as a third term of the top-level `or_(...)`.
2. In condition 3, replace `<athlete confirmed>` with
   `or_(<athlete confirmed>, _licensed(Participation.athlete_id))`. A licence
   of any season confirms an ambiguous label.

Keep the builder's docstring in step: it lists the three conditions in French.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_repositories/test_tcn_count_repository.py tests/test_layering.py -n 0 -q`
Expected: PASS on SQLite. `extract` compiles to `CAST(STRFTIME(...) AS INTEGER)`
on SQLite and to `EXTRACT(...)` on PostgreSQL; both compare to an integer.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/repositories/tcn_count_repository.py backend/tests/test_repositories/test_tcn_count_repository.py
/usr/bin/git commit -m "feat(stats): count results of known club members as TCN (#1202)"
```

---

### Task D4: `club_members_service`

**Files:**
- Create: `backend/app/services/club_members_service.py`
- Test: `backend/tests/test_services/test_club_members_service.py`

**Interfaces:**
- Consumes:
  - `fftri_club_members.fetch_club_roster`, `CLUB_URL`, `RosterUnreadableError`, `RosterMember` (D1);
  - `club_member_repository`, `athlete_repository.get_all_ranks_by_identity_keys` (D2);
  - `athlete_alias_repository.get_by_keys_batch`;
  - `tcn_count_repository.recompute_counts_for_tcn` (C, D3);
  - `sheet_source.read_table`;
  - `audit.record`.
- Produces:
  - `@dataclass(frozen=True) MembersSyncReport(season: int, total: int, linked: int, unlinked: int, ambiguous: int)`
  - `class RosterUnavailableError(DomainError)` (status 502)
  - `class MissingMemberColumnsError(DomainError)` (status 422)
  - `sync_from_fftri(db, *, user_id: int | None) -> MembersSyncReport`
  - `import_file(db, *, season: int, content: bytes, filename: str, user_id: int | None) -> MembersSyncReport`
  - `link_member(db, *, member_id: int, athlete_id: int, user_id: int | None) -> ClubMember`
  - `list_season(db, season: int) -> list[ClubMember]`
  - `seasons(db) -> list[int]`
  - `report_of(season: int, members: list[ClubMember]) -> MembersSyncReport`

None of them commits; the router and the CLI commit.

- [ ] **Step 1: Write the failing tests**

```python
"""Licenciés du club : synchro FFTri, import de fichier, rattachement (#1202)."""
from datetime import date

import pytest

from app.core.exceptions import DomainError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.club_member import (
    LINK_AMBIGUOUS, LINK_AUTO, LINK_MANUAL, LINK_UNLINKED, SOURCE_FILE, SOURCE_FFTRI,
)
from app.repositories import (
    athlete_alias_repository, club_member_repository, course_repository,
    participation_repository, user_repository,
)
from app.scrapers.fftri_club_members import ClubRoster, RosterMember, RosterUnreadableError
from app.services import club_members_service


def _athlete(db, nom, prenom, **fields):
    athlete = Athlete(nom=nom, prenom=prenom, **fields)
    db.add(athlete)
    db.flush()
    return athlete


@pytest.fixture
def admin(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    return user


@pytest.fixture
def roster(monkeypatch):
    members = [
        RosterMember("MARTIN", "Anne", "F", "C1"),
        RosterMember("DURAND", "Paul", "M", "C2"),
        RosterMember("INCONNU", "Zoé", "F", "C3"),
    ]
    monkeypatch.setattr(
        club_members_service.fftri_club_members, "fetch_club_roster",
        lambda url: ClubRoster(licence_year=2027, members=members),
    )
    return members


def test_sync_stores_the_licence_season_and_links_unique_records(db_session, admin, roster):
    martin = _athlete(db_session, "Martin", "Anne")
    _athlete(db_session, "DURAND", "Paul")
    _athlete(db_session, "DURAND", "Paul", homonym_rank=1)

    report = club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    assert report == club_members_service.MembersSyncReport(
        season=2026, total=3, linked=1, unlinked=1, ambiguous=1
    )
    rows = {m.licence_id: m for m in club_member_repository.list_season(db_session, 2026)}
    assert (rows["C1"].athlete_id, rows["C1"].link_status) == (martin.id, LINK_AUTO)
    assert (rows["C2"].athlete_id, rows["C2"].link_status) == (None, LINK_AMBIGUOUS)
    assert (rows["C3"].athlete_id, rows["C3"].link_status) == (None, LINK_UNLINKED)
    assert {m.source for m in rows.values()} == {SOURCE_FFTRI}


def test_sync_links_through_a_spelling_variant(db_session, admin, roster):
    kept = _athlete(db_session, "MARTINE", "Anne")
    athlete_alias_repository.add(db_session, ("martin", "anne"), kept.id)

    club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    rows = {m.licence_id: m for m in club_member_repository.list_season(db_session, 2026)}
    assert rows["C1"].athlete_id == kept.id


def test_a_manual_link_survives_the_next_sync(db_session, admin, roster):
    chosen = _athlete(db_session, "DURAND", "Paul")
    _athlete(db_session, "DURAND", "Paul", homonym_rank=1)
    club_members_service.sync_from_fftri(db_session, user_id=admin.id)
    ambiguous = next(m for m in club_member_repository.list_season(db_session, 2026) if m.licence_id == "C2")

    club_members_service.link_member(db_session, member_id=ambiguous.id, athlete_id=chosen.id, user_id=admin.id)
    club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    again = next(m for m in club_member_repository.list_season(db_session, 2026) if m.licence_id == "C2")
    assert (again.athlete_id, again.link_status) == (chosen.id, LINK_MANUAL)


def test_sync_recomputes_the_tcn_counters(db_session, admin, roster):
    martin = _athlete(db_session, "MARTIN", "Anne")
    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=date(2026, 10, 4), event_type="triathlon-m"
    )
    result = participation_repository.create(
        db_session, athlete_id=martin.id, course_id=course.id, bib_number="1", status="finisher"
    )

    club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    db_session.refresh(result)
    assert result.counts_for_tcn


def test_sync_records_an_audit_entry(db_session, admin, roster):
    club_members_service.sync_from_fftri(db_session, user_id=admin.id)

    log = db_session.query(AdminActionLog).one()
    assert (log.action, log.entity_type, log.entity_id) == ("club_members.sync", "club_members_season", 2026)


def test_an_unreadable_page_is_a_502_domain_error(db_session, admin, monkeypatch):
    def broken(url):
        raise RosterUnreadableError("aucun licencié lu")

    monkeypatch.setattr(club_members_service.fftri_club_members, "fetch_club_roster", broken)

    with pytest.raises(club_members_service.RosterUnavailableError) as raised:
        club_members_service.sync_from_fftri(db_session, user_id=admin.id)
    assert raised.value.status_code == 502


def test_import_file_replaces_a_past_season(db_session, admin):
    martin = _athlete(db_session, "MARTIN", "Anne")
    content = "Nom;Prénom;Sexe\nMARTIN;Anne;F\nDURAND;Paul;H\n".replace(";", ",").encode()

    report = club_members_service.import_file(
        db_session, season=2024, content=content, filename="licencies.csv", user_id=admin.id
    )

    assert (report.season, report.total, report.linked, report.unlinked) == (2024, 2, 1, 1)
    rows = club_member_repository.list_season(db_session, 2024)
    assert {(m.nom, m.gender, m.source) for m in rows} == {("MARTIN", "F", SOURCE_FILE), ("DURAND", "M", SOURCE_FILE)}
    assert next(m for m in rows if m.nom == "MARTIN").athlete_id == martin.id


def test_import_file_reads_an_optional_licence_column_and_drops_duplicates(db_session, admin):
    content = b"NOM,PRENOM,Licence\nMARTIN,Anne,C1\nMARTIN,Anne,C1\n,,\n"

    report = club_members_service.import_file(
        db_session, season=2024, content=content, filename="l.csv", user_id=admin.id
    )

    assert report.total == 1
    assert club_member_repository.list_season(db_session, 2024)[0].licence_id == "C1"


def test_import_file_without_name_columns_is_refused(db_session, admin):
    with pytest.raises(club_members_service.MissingMemberColumnsError):
        club_members_service.import_file(
            db_session, season=2024, content=b"a,b\n1,2\n", filename="l.csv", user_id=admin.id
        )


def test_import_file_refuses_a_season_out_of_range(db_session, admin):
    with pytest.raises(DomainError):
        club_members_service.import_file(
            db_session, season=1990, content=b"Nom,Prenom\nA,B\n", filename="l.csv", user_id=admin.id
        )


def test_link_member_refuses_an_unknown_member_or_athlete(db_session, admin):
    with pytest.raises(NotFoundError):
        club_members_service.link_member(db_session, member_id=999, athlete_id=1, user_id=admin.id)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_services/test_club_members_service.py -n 0 -q`
Expected: FAIL, `ImportError: cannot import name 'club_members_service'`.

- [ ] **Step 3: Implement**

```python
"""Licenciés du club par saison (#1202) : synchro FFTri, fichier, rattachement.

Un licencié rattaché à une fiche fait compter pour le club les résultats de
cette fiche sur la saison de sa licence (`tcn_count_repository`). Chaque
écriture se termine donc par un recalcul complet des compteurs.

Ne commite pas : le routeur ou la commande porte la transaction.
"""
import unicodedata
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.athlete_identity import athlete_identity_keys
from app.core.exceptions import DomainError, NotFoundError
from app.core.season import SEASON_MAX, SEASON_MIN
from app.models.club_member import (
    LINK_AMBIGUOUS, LINK_AUTO, LINK_MANUAL, LINK_UNLINKED, LINKED, SOURCE_FFTRI, SOURCE_FILE,
    ClubMember,
)
from app.repositories import (
    athlete_alias_repository, athlete_repository, club_member_repository, tcn_count_repository,
)
from app.scrapers import fftri_club_members
from app.scrapers.fftri_club_members import RosterMember
from app.services import audit, sheet_source

_SEASON_ENTITY = "club_members_season"
_MEMBER_ENTITY = "club_member"

_NOM_HEADERS = {"nom", "nomdefamille", "lastname"}
_PRENOM_HEADERS = {"prenom", "firstname"}
_GENDER_HEADERS = {"sexe", "genre", "gender"}
_LICENCE_HEADERS = {"licence", "numerodelicence", "nlicence", "license"}
_GENDERS = {"f": "F", "femme": "F", "female": "F", "h": "M", "m": "M", "homme": "M", "male": "M"}


class RosterUnavailableError(DomainError):
    status_code = 502
    message = "La liste des licenciés de la FFTri est illisible ou injoignable. Réessayez plus tard."


class MissingMemberColumnsError(DomainError):
    status_code = 422
    message = "Colonnes « Nom » et « Prénom » introuvables dans ce fichier."


class SeasonOutOfRangeError(DomainError):
    status_code = 422
    message = "Saison hors de la plage acceptée."


@dataclass(frozen=True)
class MembersSyncReport:
    season: int
    total: int
    linked: int
    unlinked: int
    ambiguous: int


def report_of(season: int, members: list[ClubMember]) -> MembersSyncReport:
    statuses = [m.link_status for m in members]
    return MembersSyncReport(
        season=season,
        total=len(members),
        linked=sum(s in LINKED for s in statuses),
        unlinked=statuses.count(LINK_UNLINKED),
        ambiguous=statuses.count(LINK_AMBIGUOUS),
    )


def list_season(db: Session, season: int) -> list[ClubMember]:
    return club_member_repository.list_season(db, season)


def seasons(db: Session) -> list[int]:
    return club_member_repository.seasons(db)


def _identity(member: ClubMember | RosterMember) -> tuple:
    if member.licence_id:
        return ("licence", member.licence_id)
    return ("name", athlete_identity_keys(member.nom, member.prenom))


def _replace(db: Session, season: int, incoming: list[RosterMember], source: str) -> list[ClubMember]:
    """Remplace la saison, rattache, et garde les rattachements faits à la main."""
    manual = {
        _identity(m): m.athlete_id
        for m in club_member_repository.list_season(db, season)
        if m.link_status == LINK_MANUAL and m.athlete_id is not None
    }
    keys = [athlete_identity_keys(m.nom, m.prenom) for m in incoming]
    by_key = athlete_repository.get_all_ranks_by_identity_keys(db, keys)
    by_alias = athlete_alias_repository.get_by_keys_batch(db, keys)

    rows = []
    for member, key in zip(incoming, keys, strict=True):
        athlete_id, status = manual.get(_identity(member)), LINK_MANUAL
        if athlete_id is None:
            candidates = {a.id for a in by_key.get(key, [])}
            if key in by_alias:
                candidates.add(by_alias[key].id)
            if len(candidates) == 1:
                athlete_id, status = candidates.pop(), LINK_AUTO
            else:
                status = LINK_AMBIGUOUS if candidates else LINK_UNLINKED
        rows.append(ClubMember(
            season=season, licence_id=member.licence_id, nom=member.nom, prenom=member.prenom,
            gender=member.gender, athlete_id=athlete_id, link_status=status, source=source,
        ))
    club_member_repository.replace_season(db, season, rows)
    tcn_count_repository.recompute_counts_for_tcn(db)
    return rows


def sync_from_fftri(db: Session, *, user_id: int | None) -> MembersSyncReport:
    try:
        roster = fftri_club_members.fetch_club_roster(fftri_club_members.CLUB_URL)
    except Exception as error:
        raise RosterUnavailableError from error
    season = roster.licence_year - 1
    rows = _replace(db, season, _deduplicated(roster.members), SOURCE_FFTRI)
    audit.record(db, user_id, action="club_members.sync", entity_type=_SEASON_ENTITY, entity_id=season)
    return report_of(season, rows)


def _header_key(header: str) -> str:
    decomposed = unicodedata.normalize("NFKD", header)
    return "".join(c for c in decomposed if c.isalnum()).casefold()


def _column(headers: list[str], accepted: set[str]) -> int | None:
    return next((i for i, h in enumerate(headers) if _header_key(h) in accepted), None)


def _deduplicated(members: list[RosterMember]) -> list[RosterMember]:
    seen: dict[tuple, RosterMember] = {}
    for member in members:
        seen.setdefault(_identity(member), member)
    return list(seen.values())


def import_file(
    db: Session, *, season: int, content: bytes, filename: str, user_id: int | None
) -> MembersSyncReport:
    if not SEASON_MIN <= season <= SEASON_MAX:
        raise SeasonOutOfRangeError
    headers, lines = sheet_source.read_table(content, filename)
    nom_at, prenom_at = _column(headers, _NOM_HEADERS), _column(headers, _PRENOM_HEADERS)
    if nom_at is None or prenom_at is None:
        raise MissingMemberColumnsError
    gender_at, licence_at = _column(headers, _GENDER_HEADERS), _column(headers, _LICENCE_HEADERS)

    def cell(line: list[str], at: int | None) -> str:
        return line[at].strip() if at is not None and at < len(line) else ""

    members = [
        RosterMember(
            nom=cell(line, nom_at),
            prenom=cell(line, prenom_at),
            gender=_GENDERS.get(cell(line, gender_at).casefold(), ""),
            licence_id=cell(line, licence_at) or None,
        )
        for line in lines
        if cell(line, nom_at)
    ]
    rows = _replace(db, season, _deduplicated(members), SOURCE_FILE)
    audit.record(db, user_id, action="club_members.import", entity_type=_SEASON_ENTITY, entity_id=season)
    return report_of(season, rows)


def link_member(db: Session, *, member_id: int, athlete_id: int, user_id: int | None) -> ClubMember:
    member = club_member_repository.get(db, member_id)
    if member is None:
        raise NotFoundError("Ce licencié n'existe pas.")
    if athlete_repository.get(db, athlete_id) is None:
        raise NotFoundError("Cette fiche d'athlète n'existe pas.")
    member.athlete_id, member.link_status = athlete_id, LINK_MANUAL
    db.flush()
    tcn_count_repository.recompute_counts_for_tcn(db)
    audit.record(
        db, user_id, action="club_member.link", entity_type=_MEMBER_ENTITY, entity_id=member.id,
        payload={"athlete_id": athlete_id},
    )
    return member
```

Notes:
- The `except Exception` in `sync_from_fftri` is deliberate: an HTTP error, a
  `BlockedTargetError` or a `RosterUnreadableError` all mean « the source is
  unavailable » for the admin. Log it with
  `logger.warning("FFTri roster unavailable", exc_info=True)` before
  re-raising, so Sentry keeps the cause.
- `sync_from_fftri` deduplicates too, so a doubled entry on the page cannot
  trip the unique constraint.
- `athlete_repository.get` exists already (`get(db, athlete_id)`).
- If `athlete_alias_repository.add` takes different arguments than in the
  test, follow its signature.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_services/test_club_members_service.py tests/test_service_boundaries.py tests/test_layering.py -n 0 -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/services/club_members_service.py backend/tests/test_services/test_club_members_service.py
/usr/bin/git commit -m "feat(members): sync, import and link club members (#1202)"
```

---

### Task D5: Permission, shared upload helper, admin API

**Files:**
- Modify: `backend/app/core/permissions.py` (new feature, permission, entry in `ALL`)
- Modify: `backend/tests/test_core/test_permissions.py` (`CODES_ATTENDUS`)
- Create: `backend/app/api/uploads.py`
- Modify: `backend/app/api/v1/admin_batches.py`, which uses `read_bounded_upload`
  and `FileTooLargeError` from `app.api.uploads` and drops its own copies
- Create: `backend/app/schemas/club_member.py`
- Create: `backend/app/api/v1/admin_club_members.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `docs/api/admin-donnees.md`, adding a « Licenciés du club (#1202) »
  section with the four routes
- Test: `backend/tests/test_api/test_admin_club_members_api.py`

**Interfaces:**
- Consumes: `club_members_service` (D4).
- Produces:
  - `P.CLUB_MEMBERS_MANAGE`, code `club_members:manage`;
  - `read_bounded_upload(file: UploadFile) -> bytes`, `FileTooLargeError`, `MAX_UPLOAD_BYTES`;
  - routes:
    - `GET /api/v1/admin/club-members?season=` → `ClubMembersSeasonOut`
    - `POST /api/v1/admin/club-members/sync` → `MembersSyncReportOut`
    - `POST /api/v1/admin/club-members/import` (multipart `season`, `file`) → `MembersSyncReportOut`
    - `POST /api/v1/admin/club-members/{member_id}/link` (`{"athlete_id": int}`) → `ClubMemberOut`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_api/test_admin_club_members_api.py`:

```python
"""Licenciés du club, écran d'administration (#1202)."""
import pytest

from app.models.athlete import Athlete
from app.models.club_member import LINK_MANUAL
from app.scrapers.fftri_club_members import ClubRoster, RosterMember
from app.services import club_members_service

from .test_admin_data_api import _session_etroite


@pytest.fixture
def roster(monkeypatch):
    monkeypatch.setattr(
        club_members_service.fftri_club_members, "fetch_club_roster",
        lambda url: ClubRoster(licence_year=2027, members=[RosterMember("MARTIN", "Anne", "F", "C1")]),
    )


def test_sync_then_read_the_season(client, db_session, roster):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.commit()

    synced = client.post("/api/v1/admin/club-members/sync")
    assert synced.status_code == 200
    assert synced.json() == {"season": 2026, "total": 1, "linked": 1, "unlinked": 0, "ambiguous": 0}

    read = client.get("/api/v1/admin/club-members", params={"season": 2026})
    assert read.status_code == 200
    body = read.json()
    assert body["seasons"] == [2026]
    assert body["members"][0] | {"id": 0} == {
        "id": 0, "season": 2026, "licence_id": "C1", "nom": "MARTIN", "prenom": "Anne",
        "gender": "F", "athlete_id": athlete.id, "link_status": "auto", "source": "fftri",
    }


def test_import_a_past_season_from_a_file(client):
    response = client.post(
        "/api/v1/admin/club-members/import",
        data={"season": "2024"},
        files={"file": ("licencies.csv", b"Nom,Prenom\nDURAND,Paul\n", "text/csv")},
    )

    assert response.status_code == 200
    assert response.json()["season"] == 2024
    assert response.json()["unlinked"] == 1


def test_a_file_too_large_is_refused(client):
    response = client.post(
        "/api/v1/admin/club-members/import",
        data={"season": "2024"},
        files={"file": ("l.csv", b"x" * (2 * 1024 * 1024 + 1), "text/csv")},
    )

    assert response.status_code == 413


def test_link_a_member_by_hand(client, db_session, roster):
    client.post("/api/v1/admin/club-members/sync")
    other = Athlete(nom="MARTIN", prenom="Anne-Marie")
    db_session.add(other)
    db_session.commit()
    member_id = client.get("/api/v1/admin/club-members", params={"season": 2026}).json()["members"][0]["id"]

    response = client.post(f"/api/v1/admin/club-members/{member_id}/link", json={"athlete_id": other.id})

    assert response.status_code == 200
    assert (response.json()["athlete_id"], response.json()["link_status"]) == (other.id, LINK_MANUAL)


def test_every_route_requires_the_permission(client, db_session):
    _session_etroite(client, db_session, "athletes:read")

    assert client.get("/api/v1/admin/club-members", params={"season": 2026}).status_code == 403
    assert client.post("/api/v1/admin/club-members/sync").status_code == 403
    assert client.post("/api/v1/admin/club-members/1/link", json={"athlete_id": 1}).status_code == 403
```

Update `CODES_ATTENDUS` in `backend/tests/test_core/test_permissions.py`: add
`"club_members:manage",` right after `"club_aliases:manage",`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_api/test_admin_club_members_api.py tests/test_core/test_permissions.py -n 0 -q`
Expected: FAIL, 404 on the routes and a catalogue mismatch.

- [ ] **Step 3: Implement**

`backend/app/core/permissions.py`:

```python
#: Licenciés du club par saison (#1202) : une liste nominative, distincte de la
#: portée des compteurs dont elle change pourtant le résultat.
FEATURE_CLUB_MEMBERS = "Licenciés du club"
```

In `class P`, after `CLUB_ALIASES_MANAGE`:

```python
    CLUB_MEMBERS_MANAGE = Permission(
        "club_members:manage",
        "Gérer les licenciés du club",
        "Relire la liste des licenciés publiée par la FFTri, importer celle "
        "d'une saison passée et rattacher un licencié à sa fiche. Un licencié "
        "rattaché fait compter ses résultats de la saison comme résultats du club.",
        FEATURE_CLUB_MEMBERS,
    )
```

In `ALL`, insert `P.CLUB_MEMBERS_MANAGE,` after `P.CLUB_ALIASES_MANAGE,`.

`backend/app/api/uploads.py`:

```python
"""Lecture bornée d'un fichier téléversé, commune aux écrans d'import (#47, #1202)."""
from fastapi import UploadFile

from app.core.exceptions import DomainError

#: Deux méga-octets : largement au-dessus de tout export du club, largement en
#: dessous de ce qui met un process web à genoux.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class FileTooLargeError(DomainError):
    status_code = 413
    message = "Fichier trop volumineux : la limite est de 2 Mo."


async def read_bounded_upload(file: UploadFile) -> bytes:
    """Lit le corps **par morceaux**, en comptant au fur et à mesure.

    Jamais d'après `Content-Length` : c'est un en-tête écrit par le client, et
    un client qui ment sur la taille est exactement celui dont on se garde.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(64 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise FileTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)
```

In `admin_batches.py`, delete `TAILLE_MAX`, `FileTooLargeError` and
`_lire_borne`, import `read_bounded_upload` from `app.api.uploads`, and replace
both `await _lire_borne(file)` calls. Then run
`grep -rn "TAILLE_MAX\|_lire_borne\|admin_batches.FileTooLargeError" backend`
and repoint any test reference to `app.api.uploads`.

`backend/app/schemas/club_member.py`:

```python
"""DTO des licenciés du club (#1202)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt


class ClubMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    licence_id: str | None
    nom: str
    prenom: str
    gender: str
    athlete_id: int | None
    link_status: Literal["auto", "manual", "unlinked", "ambiguous"]
    source: Literal["fftri", "file"]


class ClubMembersSeasonOut(BaseModel):
    season: int
    seasons: list[int]
    total: int
    linked: int
    unlinked: int
    ambiguous: int
    members: list[ClubMemberOut]


class MembersSyncReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: int
    total: int
    linked: int
    unlinked: int
    ambiguous: int


class ClubMemberLinkIn(BaseModel):
    athlete_id: StrictInt
```

`backend/app/api/v1/admin_club_members.py`:

```python
"""Licenciés du club par saison (#1202).

Routeur fin : validation et délégation au service, qui recalcule les
compteurs ; le routeur commite. Chaque route porte sa garde.
"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.uploads import read_bounded_upload
from app.core.database import get_db
from app.core.permissions import P
from app.core.season import SEASON_MAX, SEASON_MIN
from app.models.user import User
from app.schemas.club_member import (
    ClubMemberLinkIn,
    ClubMemberOut,
    ClubMembersSeasonOut,
    MembersSyncReportOut,
)
from app.services import club_members_service

router = APIRouter(tags=["admin"])


@router.get("/admin/club-members", response_model=ClubMembersSeasonOut)
def list_club_members(
    season: int = Query(..., ge=SEASON_MIN, le=SEASON_MAX),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    members = club_members_service.list_season(db, season)
    report = club_members_service.report_of(season, members)
    return ClubMembersSeasonOut(
        **MembersSyncReportOut.model_validate(report).model_dump(),
        seasons=club_members_service.seasons(db),
        members=[ClubMemberOut.model_validate(m) for m in members],
    )


@router.post("/admin/club-members/sync", response_model=MembersSyncReportOut)
def sync_club_members(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    report = club_members_service.sync_from_fftri(db, user_id=actor.id)
    db.commit()
    return report


@router.post("/admin/club-members/import", response_model=MembersSyncReportOut)
async def import_club_members(
    season: int = Form(..., ge=SEASON_MIN, le=SEASON_MAX),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    content = await read_bounded_upload(file)
    report = club_members_service.import_file(
        db, season=season, content=content, filename=file.filename or "", user_id=actor.id
    )
    db.commit()
    return report


@router.post("/admin/club-members/{member_id}/link", response_model=ClubMemberOut)
def link_club_member(
    member_id: int,
    body: ClubMemberLinkIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(P.CLUB_MEMBERS_MANAGE)),
):
    member = club_members_service.link_member(
        db, member_id=member_id, athlete_id=body.athlete_id, user_id=actor.id
    )
    db.commit()
    return ClubMemberOut.model_validate(member)
```

Register in `backend/app/api/v1/router.py`: add `admin_club_members` to the
module import list next to `admin_counter_scope`, and add its
`include_router` line at the same place as `admin_counter_scope.router`.

`MembersSyncReport` is a frozen dataclass, and `from_attributes=True` lets
`response_model` serialise it directly.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_api/test_admin_club_members_api.py tests/test_core/test_permissions.py tests/test_permissions_catalogue.py tests/test_auth/test_admin_batches_api.py -n 0 -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/core/permissions.py backend/tests/test_core/test_permissions.py backend/app/api/uploads.py backend/app/api/v1/admin_batches.py backend/app/schemas/club_member.py backend/app/api/v1/admin_club_members.py backend/app/api/v1/router.py backend/tests/test_api/test_admin_club_members_api.py docs/api/admin-donnees.md
/usr/bin/git commit -m "feat(members): admin API for club members (#1202)"
```

---

### Task D6: CLI `sync-club-members` and weekly batch step

**Files:**
- Create: `backend/app/cli/commands/sync_club_members.py`
- Modify: `backend/app/cli/__init__.py`
- Modify: `backend/app/cli/reports.py`, adding `render_members_sync_report`
- Modify: `backend/app/cli/AGENTS.md`, adding the command to the list:
  `uv run python -m app.cli sync-club-members --json   # licenciés FFTri de la saison en cours (#1202)`
- Modify: `.github/workflows/batch.yml`
- Test: `backend/tests/test_cli/test_sync_club_members.py`

**Interfaces:**
- Consumes: `club_members_service.sync_from_fftri`, `MembersSyncReport` (D4).
- Produces: command `sync-club-members [--json]`.

- [ ] **Step 1: Write the failing test**

```python
"""La commande `sync-club-members` (#1202)."""
import json

from typer.testing import CliRunner

from app.cli import app
from app.cli.commands import sync_club_members as cmd
from app.scrapers.fftri_club_members import ClubRoster, RosterMember
from app.services import club_members_service

runner = CliRunner()


def _roster(monkeypatch):
    monkeypatch.setattr(
        club_members_service.fftri_club_members, "fetch_club_roster",
        lambda url: ClubRoster(licence_year=2027, members=[RosterMember("MARTIN", "Anne", "F", "C1")]),
    )


def test_json_report_on_stdout(brancher_session, monkeypatch):
    brancher_session(cmd)
    _roster(monkeypatch)

    result = runner.invoke(app, ["sync-club-members", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "season": 2026, "total": 1, "linked": 0, "unlinked": 1, "ambiguous": 0,
    }


def test_french_report(brancher_session, monkeypatch):
    brancher_session(cmd)
    _roster(monkeypatch)

    result = runner.invoke(app, ["sync-club-members"])

    assert result.exit_code == 0
    assert "LICENCIÉS DU CLUB" in result.output
    assert "Saison 2026" in result.output


def test_an_unreachable_page_fails_the_command(brancher_session, monkeypatch):
    brancher_session(cmd)

    def broken(url):
        raise RuntimeError("boom")

    monkeypatch.setattr(club_members_service.fftri_club_members, "fetch_club_roster", broken)

    result = runner.invoke(app, ["sync-club-members"])

    assert result.exit_code == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest tests/test_cli/test_sync_club_members.py -n 0 -q`
Expected: FAIL, `ImportError` on `sync_club_members`.

- [ ] **Step 3: Implement**

`backend/app/cli/commands/sync_club_members.py`:

```python
"""Commande `sync-club-members` : relit les licenciés FFTri de la saison (#1202). Zéro logique métier.

Lancée par le batch hebdomadaire (`.github/workflows/batch.yml`), après la purge.
"""
from dataclasses import asdict

import typer

from app.cli.reports import emit_report, render_members_sync_report
from app.core.database import session_scope
from app.core.exceptions import DomainError
from app.services import club_members_service


def sync_club_members(
    json_output: bool = typer.Option(
        False, "--json",
        help="stdout ne contient que le JSON ; le rapport texte passe sur stderr.",
    ),
) -> None:
    """Remplace la liste des licenciés de la saison en cours par celle de la FFTri."""
    try:
        with session_scope() as db:
            report = club_members_service.sync_from_fftri(db, user_id=None)
            db.commit()
    except DomainError as error:
        typer.echo(error.message, err=True)
        raise typer.Exit(code=1) from error

    emit_report(render_members_sync_report(report), asdict(report), json_output=json_output)
```

Check `session_scope`: if it commits on exit, drop the explicit `db.commit()`
(read `app/core/database.py`, and follow what `backfill_genders` relies on).

In `backend/app/cli/reports.py`, next to `render_retention_report`:

```python
def render_members_sync_report(report: MembersSyncReport) -> str:
    """Synchro des licenciés FFTri (#1202)."""
    return "\n".join([
        "=== LICENCIÉS DU CLUB ===",
        f"Saison {report.season}",
        _ligne("Licenciés lus", report.total),
        _ligne("Rattachés à une fiche", report.linked),
        _ligne("Sans fiche", report.unlinked),
        _ligne("Plusieurs fiches possibles", report.ambiguous),
    ])
```

Import `MembersSyncReport` from `app.services.club_members_service` in the
same way `RetentionOutcome` is imported there.

In `backend/app/cli/__init__.py`, import `sync_club_members` and register
`app.command("sync-club-members")(sync_club_members)` in alphabetical order.

In `.github/workflows/batch.yml`, after the « Purge expired personal data »
step:

```yaml
      # Licenciés du club (#1202) : la liste FFTri de la saison en cours fait
      # compter les résultats des membres sans libellé de club. Une page
      # illisible rougit le run sans priver la base de sa reprise.
      - name: Sync club members
        id: members
        if: inputs.mode != 'urls' && inputs.dry_run != true
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: |
          set -uo pipefail
          set +e
          uv run python -m app.cli sync-club-members > members.txt 2>&1
          code=$?
          set -e
          cat members.txt
          { echo '## Licenciés du club'; echo '```'; cat members.txt; echo '```'; } >> "$GITHUB_STEP_SUMMARY"
          exit $code
```

Then extend the `Run batch` step condition so that a failed members sync does
not skip the rescrape:
`if: ${{ success() || (failure() && (steps.purge.outcome == 'failure' || steps.members.outcome == 'failure')) }}`.
If `tests/test_scraper_drift_workflow.py` or another test parses `batch.yml`,
run it as well.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_cli -n 0 -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/cli/commands/sync_club_members.py backend/app/cli/__init__.py backend/app/cli/reports.py backend/app/cli/AGENTS.md .github/workflows/batch.yml backend/tests/test_cli/test_sync_club_members.py
/usr/bin/git commit -m "feat(cli): sync-club-members command and weekly batch step (#1202)"
```

---

### Task D7: Retention of the member list

**Files:**
- Modify: `backend/app/services/retention_service.py`
- Modify: `backend/app/cli/reports.py` (`render_retention_report`)
- Test: `backend/tests/test_services/test_retention_service.py`,
  `backend/tests/test_cli/test_purge_retention.py`

**Interfaces:**
- Consumes: `club_member_repository.purge_before` (D2), `current_season`.
- Produces: `RetentionOutcome.club_members: int`;
  `club_members_cutoff(today: date) -> int` (the first season kept).

- [ ] **Step 1: Write the failing tests**

Append to `test_retention_service.py`:

```python
from app.models.athlete import Athlete
from app.models.club_member import LINK_AUTO, LINK_UNLINKED, SOURCE_FFTRI, ClubMember
from app.repositories import club_member_repository


@pytest.mark.parametrize(
    ("today", "first_kept"),
    [(date(2026, 10, 6), 2025), (date(2026, 8, 31), 2024), (date(2026, 9, 1), 2025)],
)
def test_club_members_are_kept_for_the_current_and_previous_season(today, first_kept):
    assert retention_service.club_members_cutoff(today) == first_kept


def test_purge_handles_old_member_seasons(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Anne")
    db_session.add(athlete)
    db_session.flush()
    club_member_repository.replace_season(db_session, 2023, [
        ClubMember(season=2023, nom="MARTIN", prenom="Anne", licence_id="C1", athlete_id=athlete.id,
                   link_status=LINK_AUTO, source=SOURCE_FFTRI),
        ClubMember(season=2023, nom="X", prenom="Y", licence_id="C2",
                   link_status=LINK_UNLINKED, source=SOURCE_FFTRI),
    ])

    outcome = retention_service.purge_expired(db_session, now=datetime(2026, 10, 6))

    assert outcome.club_members == 2
    (kept,) = club_member_repository.list_season(db_session, 2023)
    assert (kept.athlete_id, kept.licence_id) == (athlete.id, None)
```

Adjust the imports to what the file already has (`date`, `datetime`, `pytest`).
In `test_purge_retention.py`, update the exact JSON assertion to
`{"dry_run": True, "feedback": 1, "admin_log": 0, "profiles": 0, "club_members": 0}`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_services/test_retention_service.py tests/test_cli/test_purge_retention.py -n 0 -q`
Expected: FAIL, `AttributeError: ... club_members_cutoff` and the JSON mismatch.

- [ ] **Step 3: Implement**

In `retention_service.py`:

```python
def club_members_cutoff(today: date) -> int:
    """Première saison gardée : la saison en cours et la précédente (#1202)."""
    return season_of(today) - 1
```

Add `club_members: int` to `RetentionOutcome`, after `profiles`. In
`purge_expired`:
- dry run: `club_members=club_member_repository.purge_before(db, club_members_cutoff(now.date()), dry_run=True)`;
- real run: the same with `dry_run=False`, before `db.commit()`.

Add `club_member_repository` to the repositories import. Update the module
docstring: the durations also cover the club member list.

In `render_retention_report`, add
`_ligne(f"Licenciés de saisons anciennes {verb}", outcome.club_members),`
after the youth profiles line.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_services/test_retention_service.py tests/test_cli -n 0 -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/services/retention_service.py backend/app/cli/reports.py backend/tests/test_services/test_retention_service.py backend/tests/test_cli/test_purge_retention.py
/usr/bin/git commit -m "feat(retention): purge club member seasons after one season (#1202)"
```

---

### Task D8: Admin screen `/admin/membres`

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api/client.ts`,
  `frontend/lib/queries/keys.ts`, `frontend/lib/queries/admin.ts`
- Modify: `frontend/components/layout/nav.config.ts`
- Create: `frontend/app/admin/membres/layout.tsx`, `frontend/app/admin/membres/page.tsx`
- Create: `frontend/components/admin/ClubMembersPanel.tsx`
- Test:
  - `frontend/app/admin/membres/page.test.tsx`
  - `frontend/components/admin/ClubMembersPanel.test.tsx`
  - `frontend/app/page-titles.test.tsx` (add the route)

**Interfaces:**
- Consumes: the D5 routes.
- Produces:
  - types `ClubMember`, `ClubMembersSeason`, `MembersSyncReport`;
  - hooks `useClubMembers(season)`, `useSyncClubMembers()`,
    `useImportClubMembers()`, `useLinkClubMember()`.

- [ ] **Step 1: Write the failing tests**

`frontend/app/admin/membres/page.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";

const { useClubMembers } = vi.hoisted(() => ({ useClubMembers: vi.fn() }));

vi.mock("@/lib/queries/admin", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/queries/admin")>();
  return { ...original, useClubMembers };
});

import AdminMembresPage from "./page";

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminMembresPage />
    </QueryClientProvider>,
  );
}

describe("AdminMembresPage", () => {
  it("dit le refus une seule fois, sans offrir de geste", () => {
    useClubMembers.mockReturnValue({ data: undefined, isLoading: false, error: new ApiError(403, "Interdit") });

    afficher();

    expect(screen.getAllByText(/accès refusé/i)).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /relire la liste fftri/i })).not.toBeInTheDocument();
  });

  it("annonce les compteurs de la saison et les licenciés à rattacher", () => {
    useClubMembers.mockReturnValue({
      data: {
        season: 2026, seasons: [2026], total: 2, linked: 1, unlinked: 1, ambiguous: 0,
        members: [
          { id: 1, season: 2026, licence_id: "C1", nom: "MARTIN", prenom: "Anne", gender: "F",
            athlete_id: 5, link_status: "auto", source: "fftri" },
          { id: 2, season: 2026, licence_id: "C2", nom: "DURAND", prenom: "Paul", gender: "M",
            athlete_id: null, link_status: "unlinked", source: "fftri" },
        ],
      },
      isLoading: false,
      error: null,
    });

    afficher();

    expect(screen.getByText(/1 rattaché/i)).toBeInTheDocument();
    expect(screen.getByText("DURAND Paul")).toBeInTheDocument();
    expect(screen.queryByText("MARTIN Anne")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /relire la liste fftri/i })).toBeInTheDocument();
  });
});
```

Add `["/admin/membres", () => import("./admin/membres/layout")],` to `ECRANS` in
`frontend/app/page-titles.test.tsx`, in alphabetical order.

`frontend/components/admin/ClubMembersPanel.test.tsx` checks the import form:
it is rendered, the season defaults to the previous season, and submitting
calls the mutation with `{ season, file }`. Mock `useImportClubMembers` the
same way as above:

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mutate } = vi.hoisted(() => ({ mutate: vi.fn() }));
vi.mock("@/lib/queries/admin", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/queries/admin")>();
  return {
    ...original,
    useImportClubMembers: () => ({ mutate, isPending: false }),
    useSyncClubMembers: () => ({ mutate: vi.fn(), isPending: false }),
    useLinkClubMember: () => ({ mutate: vi.fn(), isPending: false }),
  };
});

import { ClubMembersImport } from "./ClubMembersPanel";

describe("ClubMembersImport", () => {
  it("importe le fichier pour la saison choisie", () => {
    render(<ClubMembersImport defaultSeason={2025} />);
    const fichier = new File(["Nom,Prenom\nA,B\n"], "licencies.csv", { type: "text/csv" });

    fireEvent.change(screen.getByLabelText(/fichier des licenciés/i), { target: { files: [fichier] } });
    fireEvent.click(screen.getByRole("button", { name: /importer/i }));

    expect(mutate).toHaveBeenCalledWith({ season: 2025, file: fichier }, expect.anything());
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run app/admin/membres components/admin/ClubMembersPanel.test.tsx app/page-titles.test.tsx`
Expected: FAIL, module not found.

- [ ] **Step 3: Implement**

`frontend/lib/types.ts`, appended next to the counter scope types:

```ts
/** Licenciés du club par saison (#1202). */
export type ClubMemberLinkStatus = "auto" | "manual" | "unlinked" | "ambiguous";

export interface ClubMember {
  id: number;
  season: number;
  licence_id: string | null;
  nom: string;
  prenom: string;
  gender: string;
  athlete_id: number | null;
  link_status: ClubMemberLinkStatus;
  source: "fftri" | "file";
}

export interface MembersSyncReport {
  season: number;
  total: number;
  linked: number;
  unlinked: number;
  ambiguous: number;
}

export interface ClubMembersSeason extends MembersSyncReport {
  seasons: number[];
  members: ClubMember[];
}
```

`frontend/lib/api/client.ts`, after the club alias calls (add the types to the
import list):

```ts
  // ── Licenciés du club (#1202) ──────────────────────────────────────────────
  getClubMembers: (season: number) =>
    request<ClubMembersSeason>(`/admin/club-members?season=${season}`),
  syncClubMembers: () => request<MembersSyncReport>("/admin/club-members/sync", { method: "POST" }),
  importClubMembers: (season: number, file: File) => {
    const form = new FormData();
    form.append("season", String(season));
    form.append("file", file);
    return upload<MembersSyncReport>("/admin/club-members/import", form);
  },
  linkClubMember: (memberId: number, athleteId: number) =>
    request<ClubMember>(`/admin/club-members/${memberId}/link`, {
      method: "POST",
      body: JSON.stringify({ athlete_id: athleteId }),
    }),
```

`frontend/lib/queries/keys.ts`: add
`clubMembers: (season: number) => ["club-members", season] as const,`.

`frontend/lib/queries/admin.ts`:

```ts
// ── Licenciés du club (#1202) ────────────────────────────────────────────────

export function useClubMembers(season: number) {
  return useQuery({
    queryKey: queryKeys.clubMembers(season),
    queryFn: () => apiClient.getClubMembers(season),
    retry: false,
  });
}

// Tout le cache est périmé après une écriture, même raison que
// `useAddCounterScopeEntry` : un licencié rattaché change ce que tous les
// compteurs du club additionnent.
export function useSyncClubMembers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.syncClubMembers(),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useImportClubMembers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ season, file }: { season: number; file: File }) =>
      apiClient.importClubMembers(season, file),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useLinkClubMember() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, athleteId }: { memberId: number; athleteId: number }) =>
      apiClient.linkClubMember(memberId, athleteId),
    onSuccess: () => qc.invalidateQueries(),
  });
}
```

`frontend/components/layout/nav.config.ts`, after `a-variantes-club`:

```ts
      // Liste nominative (#1202) : elle change ce que les compteurs du club
      // additionnent, comme la portée, mais par personne et par saison.
      {
        id: "a-membres",
        label: "Licenciés du club",
        description:
          "La liste des licenciés publiée par la FFTri, saison par saison. Un licencié rattaché à sa fiche fait compter ses résultats de la saison pour le club, même sans libellé de club.",
        href: "/admin/membres",
        permission: "club_members:manage",
      },
```

`frontend/app/admin/membres/layout.tsx`:

```tsx
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ecran } from "@/components/layout/nav.config";

// La page est un composant client : son titre de document vit ici (#1040).
export const metadata: Metadata = { title: ecran("/admin/membres").title };

export default function Layout({ children }: { children: ReactNode }) {
  return children;
}
```

`frontend/app/admin/membres/page.tsx`:

```tsx
"use client";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { ClubMembersPanel } from "@/components/admin/ClubMembersPanel";
import { EmptyState } from "@/components/ui/empty-state";
import { messageDeRefus } from "@/lib/api/refus";
import { useClubMembers } from "@/lib/queries/admin";
import { currentSeason } from "@/lib/utils/season";

/**
 * Licenciés du club par saison (#1202).
 *
 * Un seul pouvoir pour lire et écrire (`club_members:manage`) : un refus de
 * lecture rend l'écran entier passif, et se dit une seule fois.
 */
export default function AdminMembresPage() {
  const [season, setSeason] = useState(() => currentSeason());
  const { data, isLoading, error } = useClubMembers(season);

  return (
    <PageShell>
      <div className="space-y-10">
        <PageHeader {...ecran("/admin/membres")} />
        {error ? (
          <EmptyState
            {...messageDeRefus(error, {
              sujet: "licenciés du club",
              action: "gérer les licenciés du club",
            })}
          />
        ) : (
          <ClubMembersPanel season={season} onSeasonChange={setSeason} data={data} isLoading={isLoading} />
        )}
      </div>
    </PageShell>
  );
}
```

`frontend/components/admin/ClubMembersPanel.tsx` exports `ClubMembersPanel`,
`ClubMembersImport` and a private `LienFiche`. Follow `SheetUpload.tsx` for the
file input and `toast.error(erreur.message)` on failure, and
`MergeAthletesDialog` for the dialog around `AthleteSearchPicker`:

```tsx
"use client";
import { useState } from "react";
import { toast } from "sonner";
import { AthleteSearchPicker } from "@/components/admin/AthleteSearchPicker";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useImportClubMembers, useLinkClubMember, useSyncClubMembers } from "@/lib/queries/admin";
import type { ClubMember, ClubMembersSeason } from "@/lib/types";
import { seasonLabel } from "@/lib/utils/season";

const MOTIF: Record<ClubMember["link_status"], string> = {
  auto: "Rattaché",
  manual: "Rattaché à la main",
  unlinked: "Aucune fiche à ce nom",
  ambiguous: "Plusieurs fiches à ce nom",
};

export function ClubMembersPanel({
  season,
  onSeasonChange,
  data,
  isLoading,
}: {
  season: number;
  onSeasonChange: (season: number) => void;
  data: ClubMembersSeason | undefined;
  isLoading: boolean;
}) {
  const relire = useSyncClubMembers();
  const aRattacher = (data?.members ?? []).filter((m) => m.athlete_id === null);
  const saisons = Array.from(new Set([season, ...(data?.seasons ?? [])])).sort((a, b) => b - a);

  return (
    <div className="space-y-6">
      <Card className="space-y-4 p-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-2">
            <Label htmlFor="saison-membres">Saison</Label>
            <select
              id="saison-membres"
              className="h-9 rounded-md border px-2"
              value={season}
              onChange={(e) => onSeasonChange(Number(e.target.value))}
            >
              {saisons.map((s) => (
                <option key={s} value={s}>{seasonLabel(s)}</option>
              ))}
            </select>
          </div>
          <Button
            onClick={() =>
              relire.mutate(undefined, {
                onSuccess: (r) => {
                  onSeasonChange(r.season);
                  toast.success(`${r.total} licenciés lus pour la ${seasonLabel(r.season).toLowerCase()}.`);
                },
                onError: (erreur: Error) => toast.error(erreur.message),
              })
            }
            disabled={relire.isPending}
          >
            Relire la liste FFTri
          </Button>
        </div>
        {isLoading ? (
          <Skeleton className="h-6 w-64" />
        ) : data ? (
          <p className="text-sm">
            {data.total} licenciés : {data.linked} rattaché{data.linked > 1 ? "s" : ""}, {data.unlinked} sans
            fiche, {data.ambiguous} à départager.
          </p>
        ) : null}
      </Card>

      {aRattacher.length > 0 && (
        <Card className="space-y-3 p-6">
          <h2 className="font-semibold">Licenciés à rattacher</h2>
          <ul className="divide-y">
            {aRattacher.map((membre) => (
              <li key={membre.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  <span className="font-medium">{`${membre.nom} ${membre.prenom}`}</span>
                  <span className="ml-2 text-sm text-[var(--tcn-text-faint)]">{MOTIF[membre.link_status]}</span>
                </span>
                <LienFiche membre={membre} />
              </li>
            ))}
          </ul>
        </Card>
      )}

      <ClubMembersImport defaultSeason={season - 1} />
    </div>
  );
}

function LienFiche({ membre }: { membre: ClubMember }) {
  const [ouvert, setOuvert] = useState(false);
  const rattacher = useLinkClubMember();
  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOuvert(true)}>
        Rattacher à une fiche
      </Button>
      <Dialog open={ouvert} onOpenChange={setOuvert}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{`Rattacher ${membre.nom} ${membre.prenom}`}</DialogTitle>
          </DialogHeader>
          <AthleteSearchPicker
            selectedId={null}
            onSelect={(athlete) =>
              rattacher.mutate(
                { memberId: membre.id, athleteId: athlete.id },
                {
                  onSuccess: () => setOuvert(false),
                  onError: (erreur: Error) => toast.error(erreur.message),
                },
              )
            }
          />
        </DialogContent>
      </Dialog>
    </>
  );
}

export function ClubMembersImport({ defaultSeason }: { defaultSeason: number }) {
  const [season, setSeason] = useState(defaultSeason);
  const [fichier, setFichier] = useState<File | null>(null);
  const importer = useImportClubMembers();
  return (
    <Card className="space-y-4 p-6">
      <h2 className="font-semibold">Importer la liste d&apos;une saison passée</h2>
      <p className="text-sm text-[var(--tcn-text-faint)]">
        Un fichier .csv ou .xlsx avec une colonne « Nom » et une colonne « Prénom » (« Sexe » et « Licence » si
        possible). Il remplace toute la liste de la saison choisie.
      </p>
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="saison-import">Saison (année de début)</Label>
          <Input
            id="saison-import"
            type="number"
            value={season}
            onChange={(e) => setSeason(Number(e.target.value))}
            className="w-28"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="fichier-licencies">Fichier des licenciés (.csv ou .xlsx)</Label>
          <Input
            id="fichier-licencies"
            type="file"
            accept=".csv,.xlsx"
            onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
          />
        </div>
        <Button
          disabled={!fichier || importer.isPending}
          onClick={() =>
            fichier &&
            importer.mutate(
              { season, file: fichier },
              {
                onSuccess: (r) => toast.success(`${r.total} licenciés importés pour la ${seasonLabel(r.season).toLowerCase()}.`),
                onError: (erreur: Error) => toast.error(erreur.message),
              },
            )
          }
        >
          Importer
        </Button>
      </div>
    </Card>
  );
}
```

Check before committing:
- `seasonLabel` renders « Saison 2026 — 2027 » with an em dash. That is
  existing copy, not new prose, so leave it.
- The `<select>`: if `components/ui/select.tsx` is a Radix select, prefer it,
  following another admin page that uses it.
- `DialogContent` is a modal. If the project's `ui-ux-review` grid demands a
  description for dialogs, add a `DialogDescription`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run app/admin/membres components/admin/ClubMembersPanel.test.tsx app/page-titles.test.tsx components/layout/nav.config.test.ts && npm run lint && npx tsc --noEmit`
Expected: PASS, no lint or type error.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add frontend/lib/types.ts frontend/lib/api/client.ts frontend/lib/queries/keys.ts frontend/lib/queries/admin.ts frontend/components/layout/nav.config.ts frontend/app/admin/membres frontend/components/admin/ClubMembersPanel.tsx frontend/components/admin/ClubMembersPanel.test.tsx frontend/app/page-titles.test.tsx
/usr/bin/git commit -m "feat(frontend): admin screen for club members (#1202)"
```

---

### Task D9: RGPD, decision addendum and privacy policy

**Files:**
- Modify: `docs/superpowers/specs/2026-10-01-base-legale-decision.md`
- Modify: `frontend/components/legal/content/confidentialite.tsx`
- Test: `frontend/components/legal/content/confidentialite.test.tsx`

**Interfaces:** none (texts). The two files must agree. The decision doc wins,
per `frontend/AGENTS.md` « Textes légaux ».

- [ ] **Step 1: Write the failing test**

Append to `confidentialite.test.tsx`, inside the `describe`:

```tsx
  it("annonce la liste des licenciés, sa provenance et sa durée (#1202)", () => {
    const texte = rendre();
    expect(texte).toMatch(/liste des licenciés/i);
    expect(texte).toMatch(/Fédération Française de Triathlon/);
    expect(texte).toMatch(/numéro de licence/i);
    expect(texte).toMatch(/saison en cours et la précédente/i);
  });

  it("date la politique du jour de sa dernière modification", () => {
    expect(PRIVACY_POLICY.updatedAt).toBe("2026-10-06");
  });
```

If the second test duplicates an existing `updatedAt` assertion, update that
one instead of adding a new test.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run components/legal/content/confidentialite.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write the decision addendum**

Append to `docs/superpowers/specs/2026-10-01-base-legale-decision.md`, before
« Hors de cette décision, signalé »:

```markdown
## Avenant du 2026-10-06 : liste des licenciés du club (#1202)

**Traitement.** Le club tient, saison par saison, la liste de ses licenciés :
nom, prénom, sexe, numéro de licence, et la fiche d'athlète à laquelle chacun
est rattaché. Elle est relue chaque semaine sur la page publique du club de la
Fédération Française de Triathlon (`fftri.t2area.com`), ou importée d'un
fichier par un administrateur pour une saison passée. Elle sert à compter
comme résultats du club ceux de ses licenciés, même quand le chronométreur ne
publie pas leur club.

**Base légale.** Intérêt légitime (article 6.1.f), comme les résultats :
- les données sont déjà publiées par la fédération, dans un but voisin (faire
  connaître l'activité du club) ;
- elles ne concernent que des adhérents, qui connaissent leur club ;
- elles restent derrière le back-office : seuls les détenteurs de
  `club_members:manage` voient la liste.

**Minimisation.** Ni date de naissance, ni catégorie d'âge, ni photo, ni score
IPR, bien que la page les publie.

**Levier « ciblage des seuls adhérents » réexaminé.** Il reste écarté pour
l'affichage, qui garde le classement complet. Il ne s'agit ici que de
compter : la liste ne restreint ni n'étend ce qui est affiché.

**Conservation.** La saison en cours et la précédente, en clair. Au-delà,
`purge-retention` supprime les licenciés sans fiche, et ne garde des autres
que le fait « cette fiche était licenciée cette saison » : numéro de licence
effacé, nom et prénom ramenés à ceux de la fiche, qui suit la durée des
résultats. Sans ce fait, les compteurs des saisons passées changeraient à
chaque purge.
```

Add one row to the « Durées de conservation » table:

```markdown
| Liste des licenciés du club (#1202) | saison en cours et précédente ; ensuite, le seul rattachement à une fiche, sans numéro de licence | tenu (`purge-retention`) |
```

- [ ] **Step 4: Update the privacy policy, same commit**

In `confidentialite.tsx`:

1. `updatedAt: "2026-10-06"`.
2. In section `donnees`, after the results paragraph and its source list, add:

```tsx
          <p>
            <strong>La liste des licenciés du club.</strong> Nom, prénom, sexe et numéro de licence des
            adhérents licenciés au club, saison par saison. Elle est relue chaque semaine sur la page publique
            du club de la Fédération Française de Triathlon (T2Area), ou importée par un administrateur pour
            une saison passée. Elle sert à reconnaître comme résultats du club ceux de ses licenciés, quand le
            chronométreur ne publie pas leur club. Seuls les administrateurs habilités la consultent.
          </p>
```

3. In section `finalite`, add one list item to the reasons, after « ces
   résultats ont déjà été rendus publics… »:

```tsx
            <li>la liste des licenciés est déjà publiée par la fédération, et ne sert qu&apos;à compter ;</li>
```

4. In the `conservation` table, after « Résultats d'épreuves »:

```tsx
            ["Liste des licenciés du club", "La saison en cours et la précédente ; ensuite, seul le rattachement à la fiche de résultats est gardé, sans numéro de licence"],
```

The phrase « saison en cours et la précédente » must appear verbatim for the
test.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run components/legal && cd ../backend && uv run pytest tests/test_legal_pages.py -n 0 -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
/usr/bin/git add docs/superpowers/specs/2026-10-01-base-legale-decision.md frontend/components/legal/content/confidentialite.tsx frontend/components/legal/content/confidentialite.test.tsx
/usr/bin/git commit -m "docs(legal): declare the club member list in the privacy policy (#1202)"
```

---

### Part D exit check

Run: `cd backend && uv run pytest -m "not integration" -q && uv run ruff check . && cd ../frontend && npm test && npm run lint`
Expected: everything green. The only thing that needs real network access is a
manual check of the FFTri page:
`cd backend && uv run python -c "from app.scrapers.fftri_club_members import fetch_club_roster, CLUB_URL; r = fetch_club_roster(CLUB_URL); print(r.licence_year, len(r.members))"`.
On 2026-10-06 it printed `2027 326`.


# Partie E

## Part E: #1209 Homonymes fusionnés (séparation, revue `multi_club`, signal club à l'import)

Spec : `docs/superpowers/specs/2026-10-06-backlog-batch-b-design.md`, section 6.

**Préalables (parties A, C, D déjà livrées) :**
- A : `_Persister`, `_resolve_pending`, `_athlete_for_bib` vivent dans `backend/app/services/import_persistence.py` (code identique) ; `patch_scraper` remplace `import_dispatch.registry_scrape_event_all`.
- C : `Participation.counts_for_tcn` (bool) ; `app/repositories/tcn_count_repository.py` expose `recompute_counts_for_tcn(db, *, course_ids=None, athlete_ids=None) -> None` ; l'import recalcule la colonne des courses importées en fin de persistance.
- D : `app/models/club_member.py` `ClubMember` (`season`, `nom`, `prenom`, `athlete_id` nullable, `link_status` dans `auto`, `manual`, `unlinked`, `ambiguous`, `source`) et `club_member_repository`.

**Précisions de conception tranchées ici (cohérentes avec la spec) :**
- Clé canonique d'un club : `broad_club_key` du nom canonique (alias de club appliqués à `normalize_club`). Tous les libellés de la portée TCN partagent une seule clé, `broad_club_key(TCN_CANONICAL_NAME)`.
- « Fiche de membre TCN » : une fiche qui porte un résultat `counts_for_tcn` **ou** une licence rattachée (`ClubMember.athlete_id` non nul, `link_status` dans `auto`, `manual`).
- Motif `multi_club` : fiche de membre TCN dont les résultats individuels validés portent au moins deux clubs canoniques distincts (le TCN compte pour un), dont au moins un club significatif non confirmé. Seuls les clubs significatifs non confirmés sont listés, chacun confirmable.
- Une paire créée par l'import n'a pas d'auteur : `ignored_athlete_pairs.ignored_by_user_id` devient nullable.

**Constantes partagées par les tâches :**
- Commandes backend : `cd backend && uv run pytest -m "not integration" <chemin> -q`
- Commandes frontend : `cd frontend && npm test -- <chemin>`
- Git : `/usr/bin/git add <fichiers>` puis `/usr/bin/git commit -m "<message>"`, commandes séparées, sans trailer `Co-Authored-By`.
- Aucune ponctuation par tiret (—, –, -) dans la prose, les commentaires ou les textes d'interface.

---

### Task E1: Table `athlete_known_clubs`, auteur de paire ignorée facultatif

**Files:**
- Create: `backend/app/models/athlete_known_club.py`
- Create: `backend/app/repositories/athlete_known_club_repository.py`
- Create: `backend/alembic/versions/<rev>_athlete_known_clubs.py`
- Modify: `backend/app/models/__init__.py` (import et `__all__`)
- Modify: `backend/app/models/ignored_athlete_pair.py:27` (`ignored_by_user_id` nullable)
- Modify: `backend/app/repositories/ignored_athlete_pair_repository.py:11` (`user_id: int | None`)
- Modify: `backend/app/services/athlete_merge.py:190` (report des clubs confirmés)
- Modify: `backend/app/models/AGENTS.md` (inventaire, neuf références suivies par une fusion)
- Test: `backend/tests/test_repositories/test_athlete_known_club_repository.py`
- Test: `backend/tests/test_services/test_athlete_merge.py` (un test ajouté)

**Interfaces:**
- Produces: `AthleteKnownClub(id, athlete_id, club_key, created_at, created_by_user_id)` ; `athlete_known_club_repository.add(db, *, athlete_id: int, club_key: str, user_id: int | None) -> AthleteKnownClub`, `exists(db, *, athlete_id: int, club_key: str) -> bool`, `keys_by_athlete(db, athlete_ids: Collection[int] | None = None) -> dict[int, set[str]]` (`None` = toutes les fiches), `repoint(db, *, from_athlete_id: int, to_athlete_id: int) -> int` ; `ignored_athlete_pair_repository.create(db, *, athlete_id_a, athlete_id_b, user_id: int | None)`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_repositories/test_athlete_known_club_repository.py` :

```python
"""Clubs an admin confirmed for an athlete record (#1209)."""
from app.models.athlete import Athlete
from app.repositories import athlete_known_club_repository, ignored_athlete_pair_repository


def _athlete(db, nom="MARTIN", prenom="Thomas") -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom)
    db.add(athlete)
    db.flush()
    return athlete


def test_added_keys_are_read_back_per_athlete(db_session):
    first, second = _athlete(db_session), _athlete(db_session, "DUPONT", "Jean")
    athlete_known_club_repository.add(db_session, athlete_id=first.id, club_key="vendometriathlon", user_id=None)
    athlete_known_club_repository.add(db_session, athlete_id=first.id, club_key="asptt", user_id=None)

    assert athlete_known_club_repository.keys_by_athlete(db_session, [first.id, second.id]) == {
        first.id: {"vendometriathlon", "asptt"},
    }
    assert athlete_known_club_repository.keys_by_athlete(db_session) == {first.id: {"vendometriathlon", "asptt"}}
    assert athlete_known_club_repository.exists(db_session, athlete_id=first.id, club_key="asptt")
    assert not athlete_known_club_repository.exists(db_session, athlete_id=second.id, club_key="asptt")


def test_repoint_moves_keys_and_drops_duplicates(db_session):
    kept, absorbed = _athlete(db_session), _athlete(db_session, "MARTIN", "Tom")
    athlete_known_club_repository.add(db_session, athlete_id=kept.id, club_key="asptt", user_id=None)
    athlete_known_club_repository.add(db_session, athlete_id=absorbed.id, club_key="asptt", user_id=None)
    athlete_known_club_repository.add(db_session, athlete_id=absorbed.id, club_key="rcnantes", user_id=None)

    moved = athlete_known_club_repository.repoint(db_session, from_athlete_id=absorbed.id, to_athlete_id=kept.id)

    assert moved == 1
    assert athlete_known_club_repository.keys_by_athlete(db_session) == {kept.id: {"asptt", "rcnantes"}}


def test_an_ignored_pair_may_have_no_author(db_session):
    first, second = _athlete(db_session), _athlete(db_session, "MARTIN", "Thomas")
    pair = ignored_athlete_pair_repository.create(db_session, athlete_id_a=first.id, athlete_id_b=second.id, user_id=None)

    assert pair.ignored_by_user_id is None
```

Dans `backend/tests/test_services/test_athlete_merge.py`, ajouter (en réutilisant les helpers `_athlete` et `admin` du fichier ; adapter le nom du helper s'il diffère) :

```python
def test_a_merge_carries_the_confirmed_clubs(db_session, admin):
    from app.repositories import athlete_known_club_repository

    kept = _athlete(db_session, "MARTIN", "Thomas")
    absorbed = _athlete(db_session, "MARTIN", "Tom")
    athlete_known_club_repository.add(db_session, athlete_id=absorbed.id, club_key="asptt", user_id=None)

    athlete_merge.merge_athletes(db_session, kept_id=kept.id, absorbed_id=absorbed.id, user_id=admin.id)

    assert athlete_known_club_repository.keys_by_athlete(db_session) == {kept.id: {"asptt"}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_athlete_known_club_repository.py tests/test_services/test_athlete_merge.py -q`
Expected: FAIL, `ImportError: cannot import name 'athlete_known_club_repository'`.

- [ ] **Step 3: Implement**

`backend/app/models/athlete_known_club.py` :

```python
"""AthleteKnownClub : un club qu'un admin a confirmé pour une fiche (#1209).

Deux lecteurs : la revue d'identité (motif `multi_club`, un club confirmé n'y
signale plus rien) et l'import, qui rattache à la fiche principale un résultat
publié sous un club confirmé au lieu de créer un homonyme. `club_key` est la clé
canonique (`core.club.canonical_club_key`). `ON DELETE CASCADE` : une fiche
disparaît par plusieurs chemins, aucun ne doit penser à cette table.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class AthleteKnownClub(Base):
    __tablename__ = "athlete_known_clubs"
    __table_args__ = (UniqueConstraint("athlete_id", "club_key", name="uq_athlete_known_club"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    club_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
```

`backend/app/repositories/athlete_known_club_repository.py` :

```python
"""Accès données pour AthleteKnownClub (#1209). Ne commite jamais."""
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.athlete_known_club import AthleteKnownClub


def add(db: Session, *, athlete_id: int, club_key: str, user_id: int | None) -> AthleteKnownClub:
    known = AthleteKnownClub(athlete_id=athlete_id, club_key=club_key, created_by_user_id=user_id)
    db.add(known)
    db.flush()
    return known


def exists(db: Session, *, athlete_id: int, club_key: str) -> bool:
    return db.scalar(
        select(AthleteKnownClub.id).where(
            AthleteKnownClub.athlete_id == athlete_id, AthleteKnownClub.club_key == club_key
        )
    ) is not None


def keys_by_athlete(db: Session, athlete_ids: Collection[int] | None = None) -> dict[int, set[str]]:
    """Clubs confirmés par fiche ; `None` lit toutes les fiches (revue d'identité)."""
    query = select(AthleteKnownClub.athlete_id, AthleteKnownClub.club_key)
    if athlete_ids is not None:
        if not athlete_ids:
            return {}
        query = query.where(AthleteKnownClub.athlete_id.in_(set(athlete_ids)))
    keys: dict[int, set[str]] = {}
    for athlete_id, club_key in db.execute(query):
        keys.setdefault(athlete_id, set()).add(club_key)
    return keys


def repoint(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> int:
    """Reporte les clubs confirmés de la fiche absorbée par une fusion ; un club
    déjà confirmé sur la fiche conservée tombe. Rend le nombre de clubs reportés."""
    kept = keys_by_athlete(db, [to_athlete_id]).get(to_athlete_id, set())
    moved = 0
    for known in db.scalars(select(AthleteKnownClub).where(AthleteKnownClub.athlete_id == from_athlete_id)).all():
        if known.club_key in kept:
            db.delete(known)
        else:
            known.athlete_id = to_athlete_id
            moved += 1
    db.flush()
    return moved
```

`backend/app/models/ignored_athlete_pair.py`, ligne 27 :

```python
    # Nul pour une paire posée par l'import (#1209) : un résultat publié sous un
    # autre club qu'une fiche de membre crée un homonyme jugé distinct d'office.
    ignored_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
```

`backend/app/repositories/ignored_athlete_pair_repository.py` : signature `def create(db: Session, *, athlete_id_a: int, athlete_id_b: int, user_id: int | None) -> IgnoredAthletePair:` (corps inchangé).

`backend/app/models/__init__.py` : `from app.models.athlete_known_club import AthleteKnownClub` et `"AthleteKnownClub"` dans `__all__`, à l'ordre alphabétique des voisins.

`backend/app/services/athlete_merge.py`, après `ignored_athlete_pair_repository.repoint(...)` (et ajouter `athlete_known_club_repository` à l'import groupé des repositories) :

```python
    athlete_known_club_repository.repoint(db, from_athlete_id=absorbed.id, to_athlete_id=kept.id)
```

Migration : lancer `cd backend && uv run alembic heads` pour lire la tête courante (elle a bougé avec les parties C et D), puis `cd backend && uv run alembic revision -m "athlete known clubs"` et remplir :

```python
"""athlete known clubs

Clubs confirmés par un admin pour une fiche (#1209), et auteur facultatif d'une
paire ignorée, que l'import pose désormais sans humain.

Revision ID: <généré>
Revises: <tête lue par alembic heads>
"""
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        "athlete_known_clubs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("club_key", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("athlete_id", "club_key", name="uq_athlete_known_club"),
    )
    op.create_index("ix_athlete_known_clubs_athlete_id", "athlete_known_clubs", ["athlete_id"])
    with op.batch_alter_table("ignored_athlete_pairs") as batch:
        batch.alter_column("ignored_by_user_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM ignored_athlete_pairs WHERE ignored_by_user_id IS NULL")
    with op.batch_alter_table("ignored_athlete_pairs") as batch:
        batch.alter_column("ignored_by_user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_athlete_known_clubs_athlete_id", table_name="athlete_known_clubs")
    op.drop_table("athlete_known_clubs")
```

Garder l'en-tête `revision`, `down_revision`, `branch_labels`, `depends_on` et `__all__` du gabarit (`script.py.mako`). `created_at` reçoit sa valeur de l'ORM (`default=utcnow`), comme `ignored_athlete_pairs`.

`backend/app/models/AGENTS.md` : ajouter `AthleteKnownClub` à l'inventaire (« club confirmé pour une fiche, lu par la revue `multi_club` et l'import, #1209 ») et porter à neuf les références qu'une fusion reporte (les clubs confirmés en plus).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_athlete_known_club_repository.py tests/test_services/test_athlete_merge.py tests/test_migrations.py -q`
Expected: PASS. Puis `cd backend && uv run alembic upgrade head` sur la base de dev : sans erreur.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/models/athlete_known_club.py backend/app/models/__init__.py backend/app/models/ignored_athlete_pair.py backend/app/models/AGENTS.md backend/app/repositories/athlete_known_club_repository.py backend/app/repositories/ignored_athlete_pair_repository.py backend/app/services/athlete_merge.py backend/alembic/versions/ backend/tests/test_repositories/test_athlete_known_club_repository.py backend/tests/test_services/test_athlete_merge.py
/usr/bin/git commit -m "feat(athletes): store clubs confirmed for an athlete record (#1209)"
```

---

### Task E2: Clubs significatifs et clé canonique (`core/club.py`)

**Files:**
- Modify: `backend/app/core/club.py` (deux fonctions après `broad_club_key`)
- Test: `backend/tests/test_core/test_club.py`

**Interfaces:**
- Produces: `is_significant_club(label: str | None) -> bool` ; `canonical_club_key(label: str | None, aliases: Mapping[str, str]) -> str` (`aliases` = `club_alias_repository.canonical_map(db)` ; `""` pour un libellé vide ; la clé du TCN pour tout libellé de la portée).

- [ ] **Step 1: Write the failing tests**

Ajouter à `backend/tests/test_core/test_club.py` :

```python
from app.core.club import TCN_CANONICAL_NAME, broad_club_key, canonical_club_key, is_significant_club


def test_a_significant_club_is_a_real_club_outside_the_tcn_scope():
    assert is_significant_club("Vendôme Triathlon")
    assert not is_significant_club(None)
    assert not is_significant_club("   ")
    assert not is_significant_club("nantes (44100)")
    assert not is_significant_club("SAINT HERBLAIN (44800)")
    assert not is_significant_club("Triathlon Club Nantais")
    assert not is_significant_club("tcn")


def test_the_canonical_key_folds_aliases_case_and_accents():
    aliases = {"vendome tri": "Vendôme Triathlon"}

    assert canonical_club_key("VENDOME TRI", aliases) == broad_club_key("Vendôme Triathlon")
    assert canonical_club_key("Vendome  Triathlon", aliases) == "vendometriathlon"
    assert canonical_club_key("", aliases) == ""


def test_every_tcn_label_shares_one_key():
    tcn = broad_club_key(TCN_CANONICAL_NAME)

    assert canonical_club_key("Tri Club Nantais", {}) == tcn
    assert canonical_club_key("TCN", {}) == tcn
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_core/test_club.py -q`
Expected: FAIL, `ImportError: cannot import name 'canonical_club_key'`.

- [ ] **Step 3: Implement**

Dans `backend/app/core/club.py`, ajouter `from collections.abc import Iterable, Mapping` (remplace l'import d'`Iterable`), puis après `is_tcn` :

```python
#: Une ville publiée à la place d'un club (« nantes (44100) », format
#: runnerbreizh et Klikego `club_ou_ville`) : un lieu, pas une appartenance.
_CITY_LABEL = re.compile(r"\(\s*\d{5}\s*\)\s*$")


def is_significant_club(label: str | None) -> bool:
    """Vrai si `label` désigne un club qui sépare deux personnes (#1209) :
    non vide, pas une ville, hors de la portée TCN."""
    normalized = normalize_club(label)
    return bool(normalized) and not _CITY_LABEL.search(normalized) and not is_tcn(label)


def canonical_club_key(label: str | None, aliases: Mapping[str, str]) -> str:
    """Clé de comparaison de deux clubs (#1209) : nom canonique des alias de club
    (`club_alias_repository.canonical_map`), puis `broad_club_key`. Tous les
    libellés de la portée TCN partagent la clé du nom canonique du club."""
    if is_tcn(label):
        return broad_club_key(TCN_CANONICAL_NAME)
    normalized = normalize_club(label)
    return broad_club_key(aliases.get(normalized, normalized))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_core/test_club.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/core/club.py backend/tests/test_core/test_club.py
/usr/bin/git commit -m "feat(club): tell a significant club and its canonical key (#1209)"
```

---

### Task E3: Requêtes de fiche : membres, clubs par fiche, homonymes d'une clé

**Files:**
- Modify: `backend/app/repositories/athlete_repository.py` (trois fonctions après `review_details`)
- Test: `backend/tests/test_repositories/test_athlete_repository.py`

**Interfaces:**
- Consumes: `Participation.counts_for_tcn` (C), `ClubMember` (D).
- Produces: `member_record_ids(db, athlete_ids: Collection[int] | None = None) -> set[int]` ; `club_labels_by_athlete(db, athlete_ids: Collection[int] | None = None) -> dict[int, dict[str, int]]` (libellé brut → nombre de résultats individuels validés ; `None` = toutes les fiches qui portent au moins deux libellés normalisés distincts) ; `homonyms_of(db, key: IdentityKey) -> list[Athlete]` (rang ≥ 1, rang croissant).

- [ ] **Step 1: Write the failing tests**

Ajouter à `backend/tests/test_repositories/test_athlete_repository.py` (adapter les helpers locaux s'ils portent un autre nom ; les champs de `ClubMember` sont ceux de la partie D) :

```python
from datetime import date

from app.models.athlete import Athlete
from app.models.club_member import ClubMember
from app.repositories import athlete_repository, course_repository, participation_repository


def _course_k(db, name, *, is_relay=False):
    return course_repository.get_or_create(
        db, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m", is_relay=is_relay
    )


def _record(db, nom="MARTIN", prenom="Thomas", **fields) -> Athlete:
    athlete = Athlete(nom=nom, prenom=prenom, **fields)
    db.add(athlete)
    db.flush()
    return athlete


def test_member_records_carry_a_tcn_result_or_a_linked_licence(db_session):
    counted, licensed, outsider, pending = (_record(db_session, n) for n in ("A", "B", "C", "D"))
    participation_repository.create(
        db_session, athlete_id=counted.id, course_id=_course_k(db_session, "Tri A").id, counts_for_tcn=True
    )
    db_session.add(ClubMember(season=2026, nom="B", prenom="Thomas", athlete_id=licensed.id,
                              link_status="auto", source="fftri"))
    db_session.add(ClubMember(season=2026, nom="D", prenom="Thomas", athlete_id=pending.id,
                              link_status="ambiguous", source="fftri"))
    db_session.flush()

    assert athlete_repository.member_record_ids(db_session) == {counted.id, licensed.id}
    assert athlete_repository.member_record_ids(db_session, [counted.id, outsider.id]) == {counted.id}


def test_club_labels_count_validated_individual_results(db_session):
    athlete = _record(db_session)
    for name, club in (("Tri A", "TCN"), ("Tri B", "Vendôme Triathlon"), ("Tri C", "Vendôme Triathlon")):
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=_course_k(db_session, name).id, club=club
        )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=_course_k(db_session, "Relais", is_relay=True).id,
        club="Relais Club", is_relay=True,
    )
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=_course_k(db_session, "Tri D").id,
        club="En attente", is_pending_validation=True,
    )
    single = _record(db_session, "SEUL")
    participation_repository.create(
        db_session, athlete_id=single.id, course_id=_course_k(db_session, "Tri A").id, club="TCN"
    )

    assert athlete_repository.club_labels_by_athlete(db_session, [athlete.id]) == {
        athlete.id: {"TCN": 1, "Vendôme Triathlon": 2},
    }
    assert set(athlete_repository.club_labels_by_athlete(db_session)) == {athlete.id}


def test_homonyms_of_a_key_are_listed_by_rank(db_session):
    principal = _record(db_session)
    second = athlete_repository.create_homonym(db_session, {"nom": "MARTIN", "prenom": "Thomas"})
    third = athlete_repository.create_homonym(db_session, {"nom": "MARTIN", "prenom": "Thomas"})

    assert [a.id for a in athlete_repository.homonyms_of(db_session, ("martin", "thomas"))] == [second.id, third.id]
    assert principal.homonym_rank == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_athlete_repository.py -q -k "member_records or club_labels or homonyms_of"`
Expected: FAIL, `AttributeError: module 'app.repositories.athlete_repository' has no attribute 'member_record_ids'`.

- [ ] **Step 3: Implement**

Dans `backend/app/repositories/athlete_repository.py` (ajouter `from app.models.club_member import ClubMember` et `Collection` à l'import `collections.abc` s'il manque) :

```python
#: Statuts d'une licence rattachée à une fiche (partie D, #1202).
_LINKED = ("auto", "manual")


def member_record_ids(db: Session, athlete_ids: Collection[int] | None = None) -> set[int]:
    """Les fiches de membre TCN (#1209) : un résultat qui compte pour le club, ou
    une licence rattachée. `None` : toutes les fiches."""
    counted = select(Participation.athlete_id).where(Participation.counts_for_tcn.is_(True))
    licensed = select(ClubMember.athlete_id).where(
        ClubMember.athlete_id.is_not(None), ClubMember.link_status.in_(_LINKED)
    )
    if athlete_ids is not None:
        ids = set(athlete_ids)
        if not ids:
            return set()
        counted = counted.where(Participation.athlete_id.in_(ids))
        licensed = licensed.where(ClubMember.athlete_id.in_(ids))
    return set(db.scalars(counted.distinct())) | set(db.scalars(licensed.distinct()))


def club_labels_by_athlete(db: Session, athlete_ids: Collection[int] | None = None) -> dict[int, dict[str, int]]:
    """Libellé de club → nombre de résultats individuels validés, par fiche (#1209).

    `None` borne la lecture aux fiches qui portent au moins deux libellés
    normalisés distincts : la revue `multi_club` n'a pas à charger les autres."""
    individual = (
        Participation.club.is_not(None),
        Participation.is_relay.is_(False),
        Course.is_relay.is_(False),
        validated_clause(Participation.is_pending_validation),
    )
    query = (
        select(Participation.athlete_id, Participation.club, func.count(Participation.id))
        .join(Course, Course.id == Participation.course_id)
        .where(*individual)
        .group_by(Participation.athlete_id, Participation.club)
    )
    if athlete_ids is not None:
        ids = set(athlete_ids)
        if not ids:
            return {}
        query = query.where(Participation.athlete_id.in_(ids))
    else:
        several = (
            select(Participation.athlete_id)
            .join(Course, Course.id == Participation.course_id)
            .where(*individual)
            .group_by(Participation.athlete_id)
            .having(func.count(func.distinct(_normalise_sql(Participation.club))) > 1)
        )
        query = query.where(Participation.athlete_id.in_(several))
    labels: dict[int, dict[str, int]] = {}
    for athlete_id, club, results in db.execute(query):
        labels.setdefault(athlete_id, {})[club] = results
    return labels


def homonyms_of(db: Session, key: IdentityKey) -> list[Athlete]:
    """Les homonymes distingués d'une clé (rang ≥ 1), du plus ancien au plus récent."""
    return list(db.scalars(
        select(Athlete)
        .where(Athlete.last_name_key == key[0], Athlete.first_name_key == key[1], Athlete.homonym_rank > 0)
        .order_by(Athlete.homonym_rank)
    ))
```

`_normalise_sql` s'importe de `app.core.club` comme le fait déjà `club_alias_repository` (ajouter au `from app.core.club import ...` existant). `Course` et `validated_clause` sont déjà importés dans ce module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_repositories/test_athlete_repository.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/repositories/athlete_repository.py backend/tests/test_repositories/test_athlete_repository.py
/usr/bin/git commit -m "feat(athletes): read member records, clubs per record and homonyms of a key (#1209)"
```

---

### Task E4: Service de séparation `detach_participations`

**Files:**
- Create: `backend/app/services/athlete_detach.py`
- Test: `backend/tests/test_services/test_athlete_detach.py`

**Interfaces:**
- Consumes: `admin_actions.reassign_participation(db, *, participation_id, athlete_id, user_id)` (public), `athlete_repository.create_homonym`, `ignored_athlete_pair_repository.create`, `tcn_count_repository.recompute_counts_for_tcn` (C), `audit.record`.
- Produces: `detach_participations(db, *, athlete_id: int, participation_ids: list[int], user_id: int) -> Athlete` (rend la nouvelle fiche ; `flush` sans `commit`). Erreurs : `NotFoundError` (fiche ou résultat absent), `DomainError` (liste vide, résultat d'une autre fiche, fiche vidée), `DuplicateError` (deux résultats d'une même épreuve, via le rattachement).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_services/test_athlete_detach.py` :

```python
"""Detach results of a record onto a new homonym record (#1209)."""
from datetime import date

import pytest

from app.core.exceptions import DomainError, NotFoundError
from app.models.admin_action_log import AdminActionLog
from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import (
    course_repository,
    ignored_athlete_pair_repository,
    participation_repository,
    user_repository,
)
from app.services import athlete_detach


@pytest.fixture
def admin(db_session):
    return user_repository.create(db_session, email="admin@exemple.fr")


def _course(db, name):
    return course_repository.get_or_create(db, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m")


@pytest.fixture
def shared(db_session):
    """Une fiche qui porte les résultats de deux personnes du même nom."""
    athlete = Athlete(nom="MARTIN", prenom="Thomas", gender="M", club="Triathlon Club Nantais")
    db_session.add(athlete)
    db_session.flush()
    results = [
        participation_repository.create(
            db_session, athlete_id=athlete.id, course_id=_course(db_session, name).id, club=club, bib_number=bib
        )
        for name, club, bib in (
            ("Tri Nantes", "Triathlon Club Nantais", "1"),
            ("Tri Vendôme", "Vendôme Triathlon", "2"),
            ("Tri Blois", "Vendôme Triathlon", "3"),
        )
    ]
    return athlete, results


def test_detached_results_move_to_a_new_homonym_judged_distinct(db_session, admin, shared):
    athlete, (nantes, vendome, blois) = shared

    created = athlete_detach.detach_participations(
        db_session, athlete_id=athlete.id, participation_ids=[vendome.id, blois.id], user_id=admin.id
    )

    assert (created.nom, created.prenom, created.homonym_rank) == ("MARTIN", "Thomas", 1)
    assert created.club == "Vendôme Triathlon"
    assert {p.id for p in db_session.query(Participation).filter_by(athlete_id=created.id)} == {vendome.id, blois.id}
    assert db_session.get(Participation, nantes.id).athlete_id == athlete.id
    assert all(db_session.get(Participation, p.id).athlete_locked for p in (vendome, blois))
    assert ignored_athlete_pair_repository.exists(db_session, athlete_id_a=athlete.id, athlete_id_b=created.id)
    [log] = db_session.query(AdminActionLog).filter_by(action="athlete.detach").all()
    assert log.payload == {"from_athlete_id": athlete.id, "to_athlete_id": created.id,
                           "participation_ids": [vendome.id, blois.id]}


def test_detaching_recomputes_the_tcn_counting_of_both_records(db_session, admin, shared, monkeypatch):
    from app.repositories import tcn_count_repository

    athlete, (_, vendome, _) = shared
    calls = []
    monkeypatch.setattr(tcn_count_repository, "recompute_counts_for_tcn", lambda db, **kw: calls.append(kw))

    created = athlete_detach.detach_participations(
        db_session, athlete_id=athlete.id, participation_ids=[vendome.id], user_id=admin.id
    )

    assert calls == [{"athlete_ids": [athlete.id, created.id]}]


def test_detaching_refuses_to_empty_the_record_or_take_a_foreign_result(db_session, admin, shared):
    athlete, results = shared
    other = Athlete(nom="DUPONT", prenom="Jean")
    db_session.add(other)
    db_session.flush()
    foreign = participation_repository.create(
        db_session, athlete_id=other.id, course_id=_course(db_session, "Tri X").id
    )

    with pytest.raises(DomainError):
        athlete_detach.detach_participations(
            db_session, athlete_id=athlete.id, participation_ids=[p.id for p in results], user_id=admin.id
        )
    with pytest.raises(DomainError):
        athlete_detach.detach_participations(
            db_session, athlete_id=athlete.id, participation_ids=[foreign.id], user_id=admin.id
        )
    with pytest.raises(DomainError):
        athlete_detach.detach_participations(db_session, athlete_id=athlete.id, participation_ids=[], user_id=admin.id)
    with pytest.raises(NotFoundError):
        athlete_detach.detach_participations(db_session, athlete_id=99999, participation_ids=[1], user_id=admin.id)
    with pytest.raises(NotFoundError):
        athlete_detach.detach_participations(
            db_session, athlete_id=athlete.id, participation_ids=[99999], user_id=admin.id
        )
```

Adapter `user_repository.create(...)` à la signature réelle (voir le fixture `admin` de `tests/test_services/test_admin_actions.py`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_services/test_athlete_detach.py -q`
Expected: FAIL, `ImportError: cannot import name 'athlete_detach'`.

- [ ] **Step 3: Implement**

`backend/app/services/athlete_detach.py` :

```python
"""Séparer une fiche qui porte plusieurs personnes du même nom (#1209).

Les résultats choisis partent sur une nouvelle fiche d'homonyme, chacun par le
rattachement admin (`admin_actions.reassign_participation` : verrou d'épreuve,
refus d'un doublon sur une épreuve, résultat verrouillé contre les imports).
La paire est enregistrée comme distincte : sans elle, la reprise
`reconcile-athletes` (famille `same_key`) refusionnerait les deux fiches.
"""
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.athlete import Athlete
from app.repositories import (
    athlete_repository,
    ignored_athlete_pair_repository,
    participation_repository,
    tcn_count_repository,
)
from app.services import admin_actions, audit


def detach_participations(
    db: Session, *, athlete_id: int, participation_ids: list[int], user_id: int
) -> Athlete:
    """Déplace `participation_ids` de la fiche `athlete_id` vers une nouvelle fiche
    d'homonyme et rend celle-ci. `flush` sans `commit` : la route clôt."""
    ids = list(dict.fromkeys(participation_ids))
    if not ids:
        raise DomainError("Choisissez au moins un résultat à séparer.")
    source = athlete_repository.get(db, athlete_id)
    if source is None:
        raise NotFoundError("Athlète introuvable.")
    participations = []
    for participation_id in ids:
        participation = participation_repository.get(db, participation_id)
        if participation is None:
            raise NotFoundError("Résultat introuvable.")
        if participation.athlete_id != source.id:
            raise DomainError("Ce résultat n'appartient pas à cette fiche.")
        participations.append(participation)
    if participation_repository.count_for_athlete(db, source.id) <= len(participations):
        raise DomainError("La fiche doit garder au moins un résultat : ce serait une fusion inverse.")

    latest = max(participations, key=lambda p: (p.course.event_date is not None, p.course.event_date, p.id))
    created = athlete_repository.create_homonym(db, {
        "nom": source.nom, "prenom": source.prenom, "gender": source.gender, "club": latest.club,
    })
    for participation in participations:
        admin_actions.reassign_participation(
            db, participation_id=participation.id, athlete_id=created.id, user_id=user_id
        )
    ignored_athlete_pair_repository.create(db, athlete_id_a=source.id, athlete_id_b=created.id, user_id=user_id)
    tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=[source.id, created.id])
    audit.record(
        db, user_id, action="athlete.detach", entity_type="athlete", entity_id=source.id,
        payload={"from_athlete_id": source.id, "to_athlete_id": created.id, "participation_ids": ids},
    )
    return created
```

Si `audit.record` écrit `payload` sous un autre nom de colonne, lire `app/services/audit.py` et aligner l'assertion du test sur le modèle `AdminActionLog` (le test de `ignore_pair` dans `test_athlete_identity_review.py` montre la forme lue).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_services/test_athlete_detach.py tests/test_service_boundaries.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/services/athlete_detach.py backend/tests/test_services/test_athlete_detach.py
/usr/bin/git commit -m "feat(athletes): detach results of a shared record onto a new homonym (#1209)"
```

---

### Task E5: Route `POST /admin/athletes/{athlete_id}/detach`

**Files:**
- Modify: `backend/app/schemas/admin.py` (après `ParticipationReassign`)
- Modify: `backend/app/api/v1/admin_data.py` (route après `merge_athlete`)
- Modify: `docs/api/admin-donnees.md` (section « Séparer une fiche (#1209) » après « Fusion de deux fiches d'athlète »)
- Test: `backend/tests/test_api/test_admin_athlete_detach_api.py`

**Interfaces:**
- Consumes: `athlete_detach.detach_participations` (E4).
- Produces: `POST /api/v1/admin/athletes/{athlete_id}/detach`, corps `{"participation_ids": [int, ...]}` (1 à 500), réponse 201 `AdminAthleteRead` de la **nouvelle** fiche ; gardes `athletes:write` et `participations:reassign`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api/test_admin_athlete_detach_api.py` :

```python
"""Detach results onto a new homonym record through the admin API (#1209)."""
from datetime import date

import pytest

from app.models.athlete import Athlete
from app.repositories import course_repository, participation_repository
from tests.test_api.test_admin_data_api import _session_etroite


@pytest.fixture
def shared(db_session):
    athlete = Athlete(nom="MARTIN", prenom="Thomas")
    db_session.add(athlete)
    db_session.flush()
    results = [
        participation_repository.create(
            db_session, athlete_id=athlete.id, club=club,
            course_id=course_repository.get_or_create(
                db_session, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m"
            ).id,
        )
        for name, club in (("Tri A", "Triathlon Club Nantais"), ("Tri B", "Vendôme Triathlon"))
    ]
    db_session.commit()
    return athlete, results


def test_detaching_returns_the_new_record(client, shared):
    athlete, (_, vendome) = shared

    response = client.post(f"/api/v1/admin/athletes/{athlete.id}/detach", json={"participation_ids": [vendome.id]})

    assert response.status_code == 201
    body = response.json()
    assert body["id"] != athlete.id and (body["nom"], body["participations"]) == ("MARTIN", 1)


def test_detaching_every_result_is_refused(client, shared):
    athlete, results = shared

    response = client.post(
        f"/api/v1/admin/athletes/{athlete.id}/detach", json={"participation_ids": [p.id for p in results]}
    )

    assert response.status_code == 400


def test_detaching_needs_both_powers(client, db_session, shared):
    athlete, (_, vendome) = shared
    url = f"/api/v1/admin/athletes/{athlete.id}/detach"

    client.cookies.clear()
    assert client.post(url, json={"participation_ids": [vendome.id]}).status_code == 401
    _session_etroite(client, db_session, "athletes:write")
    assert client.post(url, json={"participation_ids": [vendome.id]}).status_code == 403
    _session_etroite(client, db_session, "participations:reassign")
    assert client.post(url, json={"participation_ids": [vendome.id]}).status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_athlete_detach_api.py -q`
Expected: FAIL, 404 sur la route.

- [ ] **Step 3: Implement**

`backend/app/schemas/admin.py`, après `ParticipationReassign` :

```python
class AthleteDetachRequest(BaseModel):
    """Les résultats d'une fiche à séparer vers une nouvelle fiche d'homonyme (#1209)."""

    participation_ids: list[StrictInt] = Field(min_length=1, max_length=500)
```

(ajouter `StrictInt` et `Field` à l'import pydantic du module s'ils manquent.)

`backend/app/api/v1/admin_data.py` : ajouter `AthleteDetachRequest` à l'import des schémas, `athlete_detach` à `from app.services import ...`, puis après `merge_athlete` :

```python
@router.post("/admin/athletes/{athlete_id}/detach", response_model=AdminAthleteRead, status_code=201)
def detach_athlete_results(
    athlete_id: int,
    body: AthleteDetachRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
    _rattachement: User = Depends(require_permission(P.PARTICIPATIONS_REASSIGN)),
):
    """Sépare des résultats vers une nouvelle fiche d'homonyme (#1209) et la rend.

    Deux pouvoirs : le geste crée une fiche (`athletes:write`) et déplace des
    résultats (`participations:reassign`)."""
    created = athlete_detach.detach_participations(
        db, athlete_id=athlete_id, participation_ids=body.participation_ids, user_id=user.id
    )
    db.commit()
    capture_event("athlete_detached", distinct_id=str(user.id), properties={"results": len(body.participation_ids)})
    return _fiche(created, participation_repository.count_for_athlete(db, created.id))
```

`docs/api/admin-donnees.md`, nouvelle section :

```markdown
## Séparer une fiche (#1209)

`POST /admin/athletes/{id}/detach` (`athletes:write` et `participations:reassign`),
corps `{"participation_ids": [...]}`. Les résultats choisis partent sur une
nouvelle fiche d'homonyme (même nom, rang suivant), chacun par le rattachement
admin (verrouillé contre les imports). La paire est enregistrée comme distincte,
pour que `reconcile-athletes` ne la refusionne pas. Rend la nouvelle fiche (201).
Refus : liste vide, résultat d'une autre fiche, fiche qui serait vidée (400),
deux résultats d'une même épreuve (409). Journal : `athlete.detach`.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_athlete_detach_api.py tests/test_api/test_admin_data_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/schemas/admin.py backend/app/api/v1/admin_data.py backend/tests/test_api/test_admin_athlete_detach_api.py docs/api/admin-donnees.md
/usr/bin/git commit -m "feat(api): admin route to detach results onto a new record (#1209)"
```

---

### Task E6: Revue `multi_club` et confirmation d'un club (service)

**Files:**
- Modify: `backend/app/services/athlete_identity_review.py`
- Modify: `backend/app/schemas/athlete_identity.py`
- Test: `backend/tests/test_services/test_athlete_identity_review.py`

**Interfaces:**
- Consumes: E1 à E3, `club_alias_repository.canonical_map`.
- Produces: motif `multi_club` (libellé « Plusieurs clubs sur une même fiche ») ; chaque candidat porte `clubs: list[{"club": str, "club_key": str, "results": int}]` (vide hors `multi_club`) ; `confirm_club(db, *, athlete_id: int, club_key: str, user_id: int) -> dict` rend `{"athlete_id", "club_key", "confirmed_at"}` ; schémas `IdentityReviewClub`, `IdentityClubConfirmCreate`, `IdentityClubConfirmOut`.

- [ ] **Step 1: Write the failing tests**

Ajouter à `backend/tests/test_services/test_athlete_identity_review.py` (helpers `_athlete`, `_course`, `_result`, `TCN` du fichier) :

```python
def _member_with_clubs(db, *clubs):
    member = _athlete(db, "MARTIN", "Thomas", club=TCN)
    for index, club in enumerate(clubs):
        _result(db, member, _course(db, f"Tri {index}"), str(index), club=club, counts_for_tcn=club == TCN)
    return member


def test_a_member_record_with_another_unconfirmed_club_is_listed(db_session):
    member = _member_with_clubs(
        db_session, TCN, "Vendôme Triathlon", "Vendôme Triathlon", "VENDOME TRIATHLON", "nantes (44100)"
    )

    [candidate] = athlete_identity_review.find_candidates(db_session)

    assert (candidate["reason"], [a["id"] for a in candidate["athletes"]]) == ("multi_club", [member.id])
    # Les deux graphies se regroupent ; la plus fréquente nomme le club ; la ville ne compte pas.
    assert candidate["clubs"] == [{"club": "Vendôme Triathlon", "club_key": "vendometriathlon", "results": 3}]


def test_a_record_outside_the_club_or_with_one_club_is_not_listed(db_session):
    outsider = _athlete(db_session, "DUPONT", "Jean")
    _result(db_session, outsider, _course(db_session, "Tri A"), "1", club="ASPTT")
    _result(db_session, outsider, _course(db_session, "Tri B"), "2", club="Vendôme Triathlon")
    _member_with_clubs(db_session, TCN, TCN)

    assert _reasons(db_session) == []


def test_a_confirmed_club_leaves_the_review(db_session, admin):
    member = _member_with_clubs(db_session, TCN, "Vendôme Triathlon")

    out = athlete_identity_review.confirm_club(
        db_session, athlete_id=member.id, club_key="vendometriathlon", user_id=admin.id
    )

    assert (out["athlete_id"], out["club_key"]) == (member.id, "vendometriathlon")
    assert _reasons(db_session) == []
    [log] = db_session.query(AdminActionLog).filter_by(action="athlete_identity.confirm_club").all()
    assert log.payload == {"club_key": "vendometriathlon"}
    with pytest.raises(DuplicateError):
        athlete_identity_review.confirm_club(
            db_session, athlete_id=member.id, club_key="vendometriathlon", user_id=admin.id
        )
    with pytest.raises(NotFoundError):
        athlete_identity_review.confirm_club(db_session, athlete_id=99999, club_key="x", user_id=admin.id)
    with pytest.raises(DomainError):
        athlete_identity_review.confirm_club(db_session, athlete_id=member.id, club_key=" ", user_id=admin.id)


def test_the_count_includes_multi_club_cases(db_session):
    _member_with_clubs(db_session, TCN, "Vendôme Triathlon")

    assert athlete_identity_review.count(db_session) == 1
```

Si le fichier n'a pas de fixture `admin`, l'ajouter sur le modèle de `test_athlete_detach.py` (E4).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_services/test_athlete_identity_review.py -q`
Expected: FAIL (`multi_club` absent, `confirm_club` inexistant).

- [ ] **Step 3: Implement**

`backend/app/schemas/athlete_identity.py` :

```python
class IdentityReviewClub(BaseModel):
    """Un club à vérifier sur une fiche (`multi_club`, #1209)."""

    club: str
    club_key: str
    results: int


class IdentityReviewCandidate(BaseModel):
    reason: str
    reason_label: str
    athletes: list[IdentityReviewAthlete]
    conflicts: list[IdentityReviewConflict]
    clubs: list[IdentityReviewClub] = []


class IdentityClubConfirmCreate(BaseModel):
    athlete_id: StrictInt
    club_key: str


class IdentityClubConfirmOut(BaseModel):
    athlete_id: int
    club_key: str
    confirmed_at: datetime
```

(`IdentityReviewCandidate` remplace la définition existante.)

`backend/app/services/athlete_identity_review.py` :

1. Docstring du module : six motifs ; ajouter après `same_course_bibs` la puce « `multi_club` : une fiche de membre dont les résultats portent un autre club, non confirmé, que les siens (#1209) ; l'admin sépare la fiche ou confirme le club ».
2. Imports : `from app.core.club import canonical_club_key, is_significant_club, is_tcn, normalize_club` ; ajouter `athlete_known_club_repository, club_alias_repository` à l'import des repositories.
3. `REASONS` (ordre d'insertion = ordre d'affichage) :

```python
REASONS = {
    "same_course_bibs": "Deux dossards sur une même épreuve",
    "multi_club": "Plusieurs clubs sur une même fiche",
    "club_homonym": "Homonymes, dont un du club",
    "swapped": "Nom et prénom inversés",
    "concatenated": "Nom complet face à une fiche découpée",
    "alias_collision": "Fiche recréée sur une graphie fusionnée",
}
```

4. Nouvelle fonction, avant `_cases` :

```python
def _unconfirmed_clubs(db: Session) -> dict[int, list[dict]]:
    """Fiches de membre et leurs clubs significatifs non confirmés (#1209).

    Une fiche n'est retenue que si ses résultats portent au moins deux clubs
    canoniques (le TCN compte pour un) dont un significatif non confirmé : un
    membre en double licence sort de la liste dès que son second club est confirmé."""
    labels = athlete_repository.club_labels_by_athlete(db)
    members = athlete_repository.member_record_ids(db, labels)
    known = athlete_known_club_repository.keys_by_athlete(db, members)
    aliases = club_alias_repository.canonical_map(db)
    cases: dict[int, list[dict]] = {}
    for athlete_id in sorted(members):
        by_key: dict[str, dict] = {}
        for label, results in labels[athlete_id].items():
            significant = is_significant_club(label)
            if not significant and not is_tcn(label):
                continue  # ville ou libellé vide : un lieu, pas un club
            key = canonical_club_key(label, aliases)
            entry = by_key.setdefault(key, {"club": label, "club_key": key, "results": 0, "top": 0,
                                            "significant": significant})
            entry["results"] += results
            if results > entry["top"]:
                entry["club"], entry["top"] = label, results
        to_check = [
            {"club": e["club"], "club_key": e["club_key"], "results": e["results"]}
            for e in by_key.values() if e["significant"] and e["club_key"] not in known.get(athlete_id, set())
        ]
        if len(by_key) >= 2 and to_check:
            cases[athlete_id] = sorted(to_check, key=lambda club: (-club["results"], club["club"]))
    return cases
```

(`is_tcn` s'importe de `app.core.club` avec les deux autres.)

5. `_cases` rend désormais `(motif, fiches, épreuves en conflit, clubs)` ; les tuples internes portent `clubs` en dernier. Après la boucle `same_course_bibs` :

```python
    for athlete_id, clubs in _unconfirmed_clubs(db).items():
        cases.append((1, athlete_id, "multi_club", [athlete_id], [], clubs))
```

décaler `club_homonym` à l'ordre 2 et `enumerate(pairs, start=3)` ; ajouter `[]` comme `clubs` à chaque `cases.append` existant ; tri inchangé (`key=lambda case: case[:2]`) ; rendre `[(reason, ids, courses, clubs) for _, _, reason, ids, courses, clubs in sorted(...)]`.

6. `find_candidates` : déballer `for reason, ids, courses, clubs in cases`, le `review_details` lit `[i for _, ids, _, _ in cases for i in ids]`, et ajouter `"clubs": clubs` au dict du candidat. `count` reste `len(_cases(db))`.

7. Après `ignore_pair` :

```python
def confirm_club(db: Session, *, athlete_id: int, club_key: str, user_id: int) -> dict:
    """Confirme qu'un club est bien celui de la personne de la fiche (#1209) : la
    revue ne le signale plus, et l'import y rattache ses résultats. `flush` sans commit."""
    key = club_key.strip()
    if not key:
        raise DomainError("Le club à confirmer est vide.")
    if athlete_repository.get(db, athlete_id) is None:
        raise NotFoundError("Athlète introuvable.")
    if athlete_known_club_repository.exists(db, athlete_id=athlete_id, club_key=key):
        raise DuplicateError("Ce club est déjà confirmé pour cette fiche.")
    known = athlete_known_club_repository.add(db, athlete_id=athlete_id, club_key=key, user_id=user_id)
    audit.record(
        db, user_id, action="athlete_identity.confirm_club", entity_type="athlete", entity_id=athlete_id,
        payload={"club_key": key},
    )
    return {"athlete_id": athlete_id, "club_key": key, "confirmed_at": known.created_at}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_services/test_athlete_identity_review.py tests/test_api/test_admin_identity_review_api.py -q`
Expected: PASS (les tests existants restent verts : `clubs` vaut `[]` hors `multi_club`).

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/services/athlete_identity_review.py backend/app/schemas/athlete_identity.py backend/tests/test_services/test_athlete_identity_review.py
/usr/bin/git commit -m "feat(athletes): review member records spanning unconfirmed clubs (#1209)"
```

---

### Task E7: Route `POST /admin/identity-review/confirm-club`

**Files:**
- Modify: `backend/app/api/v1/admin_athlete_identity.py`
- Modify: `docs/api/admin-donnees.md` (§ « Revue d'identité des athlètes (#908) » : motif `multi_club`, champ `clubs`, nouvelle route)
- Test: `backend/tests/test_api/test_admin_identity_review_api.py`

**Interfaces:**
- Consumes: `athlete_identity_review.confirm_club` (E6).
- Produces: `POST /api/v1/admin/identity-review/confirm-club`, corps `{"athlete_id": int, "club_key": str}`, 201 `{"athlete_id", "club_key", "confirmed_at"}` ; garde `athletes:write`.

- [ ] **Step 1: Write the failing test**

Ajouter à `backend/tests/test_api/test_admin_identity_review_api.py` :

```python
from datetime import date

from app.repositories import course_repository, participation_repository


@pytest.fixture
def multi_club(db_session):
    member = Athlete(nom="MARTIN", prenom="Thomas", club="Triathlon Club Nantais")
    db_session.add(member)
    db_session.flush()
    for name, club in (("Tri A", "Triathlon Club Nantais"), ("Tri B", "Vendôme Triathlon")):
        participation_repository.create(
            db_session, athlete_id=member.id, club=club, counts_for_tcn=club != "Vendôme Triathlon",
            course_id=course_repository.get_or_create(
                db_session, name=name, event_date=date(2026, 5, 16), event_type="triathlon-m"
            ).id,
        )
    db_session.commit()
    return member


def test_a_multi_club_case_lists_its_clubs_and_a_confirmation_closes_it(client, multi_club):
    [candidate] = client.get("/api/v1/admin/identity-review").json()["candidates"]
    assert candidate["reason"] == "multi_club"
    assert candidate["clubs"] == [{"club": "Vendôme Triathlon", "club_key": "vendometriathlon", "results": 1}]

    confirmed = client.post(
        "/api/v1/admin/identity-review/confirm-club",
        json={"athlete_id": multi_club.id, "club_key": "vendometriathlon"},
    )

    assert confirmed.status_code == 201
    assert client.get("/api/v1/admin/identity-review/count").json() == {"total": 0}
    again = client.post(
        "/api/v1/admin/identity-review/confirm-club",
        json={"athlete_id": multi_club.id, "club_key": "vendometriathlon"},
    )
    assert again.status_code == 409
```

et ajouter `("post", "/api/v1/admin/identity-review/confirm-club")` à la paramétrisation du test de garde, en envoyant pour ce chemin `json={"athlete_id": first.id, "club_key": "asptt"}` :

```python
    def call():
        if method == "get":
            return client.get(path)
        if path.endswith("confirm-club"):
            return client.post(path, json={"athlete_id": first.id, "club_key": "asptt"})
        return client.post(path, json={"athlete_id_a": first.id, "athlete_id_b": second.id})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_identity_review_api.py -q`
Expected: FAIL, 404/405 sur `confirm-club`.

- [ ] **Step 3: Implement**

`backend/app/api/v1/admin_athlete_identity.py` (importer `IdentityClubConfirmCreate`, `IdentityClubConfirmOut`) :

```python
@router.post("/admin/identity-review/confirm-club", response_model=IdentityClubConfirmOut, status_code=201)
def confirm_identity_club(
    body: IdentityClubConfirmCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.ATHLETES_WRITE)),
) -> IdentityClubConfirmOut:
    """Confirme un club pour une fiche (#1209) : il ne la signale plus, et l'import
    y rattache les résultats publiés sous ce club."""
    out = athlete_identity_review.confirm_club(
        db, athlete_id=body.athlete_id, club_key=body.club_key, user_id=user.id
    )
    db.commit()
    return IdentityClubConfirmOut(**out)
```

Mettre à jour la docstring du module (« lecture, compte, mise à l'écart d'une paire, confirmation d'un club »).

`docs/api/admin-donnees.md` : ajouter à la liste des motifs « `multi_club` : une fiche de membre TCN dont les résultats individuels validés portent un club significatif (ni vide, ni ville, ni libellé de la portée) non confirmé, à côté d'un autre club ; `clubs` liste les clubs à vérifier » et la route `POST /admin/identity-review/confirm-club` (`athletes:write`, 201, 409 si déjà confirmé, journal `athlete_identity.confirm_club`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_api/test_admin_identity_review_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/api/v1/admin_athlete_identity.py backend/tests/test_api/test_admin_identity_review_api.py docs/api/admin-donnees.md
/usr/bin/git commit -m "feat(api): confirm a club for an athlete record from the identity review (#1209)"
```

---

### Task E8: Import : un autre club que ceux d'une fiche de membre va sur un homonyme

**Files:**
- Modify: `backend/app/services/import_persistence.py` (`_Persister.__init__`, `_resolve_pending`, deux méthodes nouvelles)
- Test: `backend/tests/test_services/test_import_club_homonyms.py`

**Interfaces:**
- Consumes: E1 (`athlete_known_club_repository`, `ignored_athlete_pair_repository.create(user_id=None)`), E2 (`is_significant_club`, `canonical_club_key`), E3 (`member_record_ids`, `club_labels_by_athlete`, `homonyms_of`), `club_alias_repository.canonical_map`.
- Produces: entrée `homonyms_created` de même forme qu'au #967 (`course_id`, `bib`, `athlete_id`, `homonym_of`).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_services/test_import_club_homonyms.py` :

```python
"""A result under another club than a member record's goes to a homonym (#1209)."""
from datetime import date

from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import athlete_known_club_repository, ignored_athlete_pair_repository
from app.services import import_service
from tests.test_services.test_import_service import URL, _expire_cache, _result, _settings

TCN = "Triathlon Club Nantais"
VENDOME_URL = "https://www.klikego.com/resultats/event/700"
BLOIS_URL = "https://www.klikego.com/resultats/event/701"


def _import(db_session, patch_scraper, rows, url=URL) -> dict:
    patch_scraper(rows)
    out = import_service.import_event(db_session, url, _settings())
    db_session.commit()
    return out


def _elsewhere(url, club, bib="7", **kw):
    event = {VENDOME_URL: "Triathlon de Vendôme", BLOIS_URL: "Triathlon de Blois"}[url]
    return _result(bib, "MARTIN", "Thomas", club=club, source_url=url, event_name=event,
                   event_date=date(2026, 6, 20), **kw)


def _carrier(db_session, url_event: str) -> Athlete:
    return db_session.query(Participation).join(Participation.course).filter_by(name=url_event).one().athlete


def _member(db_session, patch_scraper) -> Athlete:
    _import(db_session, patch_scraper, [_result("1", "MARTIN", "Thomas", club=TCN)])
    return db_session.query(Athlete).filter_by(nom="MARTIN", homonym_rank=0).one()


def test_another_club_than_a_member_record_creates_a_distinct_homonym(db_session, patch_scraper):
    member = _member(db_session, patch_scraper)

    out = _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)

    carrier = _carrier(db_session, "Triathlon de Vendôme")
    assert carrier.id != member.id and carrier.homonym_rank == 1
    assert out["homonyms_created"] == [
        {"course_id": carrier.participations[0].course_id, "bib": "7", "athlete_id": carrier.id,
         "homonym_of": member.id},
    ]
    assert ignored_athlete_pair_repository.exists(db_session, athlete_id_a=member.id, athlete_id_b=carrier.id)


def test_the_same_other_club_later_goes_to_the_same_homonym(db_session, patch_scraper):
    _member(db_session, patch_scraper)
    _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)

    out = _import(db_session, patch_scraper, [_elsewhere(BLOIS_URL, "VENDOME TRIATHLON")], url=BLOIS_URL)

    assert _carrier(db_session, "Triathlon de Blois").id == _carrier(db_session, "Triathlon de Vendôme").id
    assert out["homonyms_created"] == []


def test_no_club_a_city_or_a_confirmed_club_stays_on_the_member(db_session, patch_scraper):
    member = _member(db_session, patch_scraper)
    athlete_known_club_repository.add(db_session, athlete_id=member.id, club_key="asptt", user_id=None)
    db_session.commit()

    _import(db_session, patch_scraper, [
        _elsewhere(VENDOME_URL, None, bib="7"),
        _result("8", "MARTIN", "Thomas", club="ASPTT", source_url=VENDOME_URL,
                event_name="Triathlon de Vendôme", event_date=date(2026, 6, 20), event_type="triathlon-s"),
    ], url=VENDOME_URL)

    assert {p.athlete_id for p in db_session.query(Participation)} == {member.id}
    _import(db_session, patch_scraper, [_elsewhere(BLOIS_URL, "nantes (44100)")], url=BLOIS_URL)
    assert _carrier(db_session, "Triathlon de Blois").id == member.id


def test_a_record_outside_the_club_keeps_every_club(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "MARTIN", "Thomas", club="AC Rezé")])

    _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)

    assert db_session.query(Athlete).filter_by(nom="MARTIN").count() == 1


def test_a_rescrape_keeps_the_homonym(db_session, patch_scraper):
    _member(db_session, patch_scraper)
    _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)
    carrier = _carrier(db_session, "Triathlon de Vendôme")
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_elsewhere(VENDOME_URL, "Vendôme Triathlon")], url=VENDOME_URL)

    assert _carrier(db_session, "Triathlon de Vendôme").id == carrier.id
    assert out["homonyms_created"] == []
```

Note : `_carrier` lit l'épreuve par son nom ; si `mapping` compose le nom de course autrement que `event_name` (lire `tests/test_services/test_import_service.py` pour un exemple de lecture d'épreuve importée), filtrer plutôt sur `Course.source_url`. Le second résultat du test « no club » vise une autre épreuve du même événement (`event_type="triathlon-s"`), sinon les deux dossards d'une même épreuve individuelle créeraient un homonyme #967. Si la clé d'identité de course de `_result` diffère, lire `test_import_homonyms.py` pour la forme d'une seconde épreuve.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest -m "not integration" tests/test_services/test_import_club_homonyms.py -q`
Expected: FAIL sur les tests de routage (`carrier.id == member.id`).

- [ ] **Step 3: Implement**

Dans `backend/app/services/import_persistence.py` :

Imports : `from app.core.club import canonical_club_key, is_significant_club` ; ajouter `athlete_known_club_repository, club_alias_repository, ignored_athlete_pair_repository` à l'import des repositories.

`_Persister.__init__`, après `self._created_for_bibs` :

```python
        # Signal de club (#1209) : alias lus une fois, et l'homonyme choisi pour
        # chaque couple (clé d'identité, club) de ce scrape.
        self._club_aliases: dict[str, str] = club_alias_repository.canonical_map(db)
        self._club_homonyms: dict[tuple[IdentityKey, str], Athlete] = {}
```

`_resolve_pending`, juste après `latest_clubs = athlete_repository.latest_club_dates(...)` :

```python
        # Une requête par tranche, bornée aux fiches de membre qu'une ligne d'un
        # autre club pourrait viser (#1209).
        member_clubs = self._member_club_keys({
            found[_identity_key(item.scraped)].id
            for item, teammates, record in zip(pending, decisions, kept, strict=True)
            if teammates is None and record is None and item.participation is None
            and not item.reconcile_blocked and not item.scraped.is_relay
            and not self._courses[course_id].is_relay and is_significant_club(item.scraped.club)
        })
```

Dans la boucle, remplacer :

```python
            key = _identity_key(item.scraped)
            athlete = record or found[key]
            created_for_bib = False
            if record is None and item.bib is not None:
                resolved, athlete = athlete, self._athlete_for_bib(course_id, item, athlete)
                created_for_bib = athlete is not resolved and athlete.id in self._created_for_bibs
```

par :

```python
            key = _identity_key(item.scraped)
            athlete = resolved = record or found[key]
            if record is None and item.participation is None and athlete.id in member_clubs:
                athlete = self._athlete_for_club(course_id, item, athlete, member_clubs[athlete.id])
            if record is None and item.bib is not None:
                athlete = self._athlete_for_bib(course_id, item, athlete)
            created_for_bib = athlete is not resolved and athlete.id in self._created_for_bibs
```

Nouvelles méthodes, après `_athlete_for_bib` :

```python
    def _club_keys(self, athlete_ids: set[int]) -> dict[int, set[str]]:
        """Clubs d'une fiche : ceux de ses résultats et ceux qu'un admin a confirmés."""
        labels = athlete_repository.club_labels_by_athlete(self.db, athlete_ids)
        known = athlete_known_club_repository.keys_by_athlete(self.db, athlete_ids)
        return {
            athlete_id: {
                canonical_club_key(label, self._club_aliases) for label in labels.get(athlete_id, {})
            } | known.get(athlete_id, set())
            for athlete_id in athlete_ids
        }

    def _member_club_keys(self, athlete_ids: set[int]) -> dict[int, set[str]]:
        """Les clubs des seules fiches de membre TCN parmi `athlete_ids` (#1209)."""
        if not athlete_ids:
            return {}
        return self._club_keys(athlete_repository.member_record_ids(self.db, athlete_ids))

    def _athlete_for_club(
        self, course_id: int, item: _PendingResolution, athlete: Athlete, known_keys: set[str]
    ) -> Athlete:
        """La fiche d'une ligne publiée sous un autre club que ceux d'une fiche de
        membre (#1209) : l'homonyme de même nom qui porte déjà ce club, sinon un
        nouvel homonyme, jugé distinct d'office pour que la reprise ne le refusionne
        pas. Une fiche trouvée par variante ou par repli n'a pas la clé de la
        ligne : rien n'est décidé sur elle."""
        club_key = canonical_club_key(item.scraped.club, self._club_aliases)
        identity = _identity_key(item.scraped)
        if club_key in known_keys or (athlete.last_name_key, athlete.first_name_key) != identity:
            return athlete
        routed = self._club_homonyms.get((identity, club_key))
        if routed is None:
            homonyms = athlete_repository.homonyms_of(self.db, identity)
            clubs = self._club_keys({homonym.id for homonym in homonyms})
            routed = next((homonym for homonym in homonyms if club_key in clubs[homonym.id]), None)
        if routed is None:
            routed = athlete_repository.create_homonym(self.db, mapping.athlete_creation_fields(item.scraped))
            ignored_athlete_pair_repository.create(
                self.db, athlete_id_a=athlete.id, athlete_id_b=routed.id, user_id=None
            )
            self._created_for_bibs.add(routed.id)
            self.homonyms_created.append({
                "course_id": course_id, "bib": item.bib, "athlete_id": routed.id, "homonym_of": athlete.id,
            })
        self._club_homonyms[(identity, club_key)] = routed
        return routed
```

Mettre à jour la docstring de `_resolve_pending` : ajouter « Une ligne d'un autre club qu'une fiche de membre part sur un homonyme (#1209, `_athlete_for_club`). »

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest -m "not integration" tests/test_services/test_import_club_homonyms.py tests/test_services/test_import_homonyms.py tests/test_services/test_import_identity.py tests/test_services/test_import_service.py tests/test_services/test_admin_corrections_survive.py -q`
Expected: PASS. Puis la suite complète : `cd backend && uv run pytest -m "not integration" -q`, verte.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add backend/app/services/import_persistence.py backend/tests/test_services/test_import_club_homonyms.py
/usr/bin/git commit -m "feat(import): route a result under another club than a member record to a homonym (#1209)"
```

---

### Task E9: Front : séparer des résultats depuis la fiche athlète

**Files:**
- Modify: `frontend/lib/api/client.ts` (après `mergeAthletes`)
- Modify: `frontend/lib/queries/admin.ts` (après `useReassignParticipation`)
- Create: `frontend/components/athletes/AthleteDetachAction.tsx`
- Create: `frontend/components/athletes/AthleteDetachAction.test.tsx`
- Modify: `frontend/app/(public_restricted)/athletes/[id]/EventsTable.tsx` (en-tête de la carte, l.241-244)

**Interfaces:**
- Consumes: `POST /admin/athletes/{id}/detach` (E5).
- Produces: `apiClient.detachParticipations(athleteId: number, participationIds: number[]) => Promise<AdminAthlete>` ; `useDetachParticipations()` (mutation `{ athleteId, participationIds }`) ; `<AthleteDetachAction athleteId athleteName participations />`.

- [ ] **Step 1: Write the failing test**

`frontend/components/athletes/AthleteDetachAction.test.tsx` :

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Participation, SessionUser } from "@/lib/types";

const { getSession, detachParticipations, push, toastSuccess, toastError } = vi.hoisted(() => ({
  getSession: vi.fn(),
  detachParticipations: vi.fn(),
  push: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getSession, detachParticipations } };
});
vi.mock("sonner", () => ({ toast: { success: toastSuccess, error: toastError } }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));

import { AthleteDetachAction } from "./AthleteDetachAction";

function session(permissions: string[]): SessionUser {
  return { id: 1, email: "a@exemple.fr", permissions, roles: [], created_at: "2026-01-01T00:00:00Z" } as unknown as SessionUser;
}

const RESULTAT = (id: number, nom: string, club: string | null) =>
  ({ id, club, course: { id: id * 10, name: nom, event_date: "2026-05-16" } }) as unknown as Participation;

const RESULTATS = [RESULTAT(1, "Tri Nantes", "Triathlon Club Nantais"), RESULTAT(2, "Tri Vendôme", "Vendôme Triathlon")];

function afficher(participations = RESULTATS) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AthleteDetachAction athleteId={7} athleteName="MARTIN Thomas" participations={participations} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  document.cookie = "tcn_logged_in=1; path=/";
});

describe("AthleteDetachAction", () => {
  it("n'est pas offert sans les deux pouvoirs", async () => {
    getSession.mockResolvedValue(session(["athletes:write"]));
    afficher();
    await vi.waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /séparer/i })).not.toBeInTheDocument();
  });

  it("n'est pas offert sur une fiche à un seul résultat", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "participations:reassign"]));
    afficher([RESULTATS[0]]);
    await vi.waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /séparer/i })).not.toBeInTheDocument();
  });

  it("sépare les résultats cochés après confirmation, puis ouvre la nouvelle fiche", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "participations:reassign"]));
    detachParticipations.mockResolvedValue({ id: 42, nom: "MARTIN", prenom: "Thomas" });
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: "Séparer des résultats de MARTIN Thomas" }));
    const choix = await screen.findByRole("dialog");
    const envoi = within(choix).getByRole("button", { name: "Séparer vers une nouvelle fiche" });
    expect(envoi).toBeDisabled();
    await userEvent.click(within(choix).getByRole("checkbox", { name: /Tri Vendôme/ }));
    await userEvent.click(envoi);

    const confirmation = await screen.findByRole("dialog", { name: /Séparer 1 résultat/ });
    await userEvent.click(within(confirmation).getByRole("button", { name: "Séparer" }));

    expect(detachParticipations).toHaveBeenCalledWith(7, [2]);
    expect(push).toHaveBeenCalledWith("/athletes/42");
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("tout cocher laisse l'envoi inerte : la fiche doit garder un résultat", async () => {
    getSession.mockResolvedValue(session(["athletes:write", "participations:reassign"]));
    afficher();

    await userEvent.click(await screen.findByRole("button", { name: /Séparer des résultats/ }));
    const choix = await screen.findByRole("dialog");
    for (const caseACocher of within(choix).getAllByRole("checkbox")) await userEvent.click(caseACocher);

    expect(within(choix).getByRole("button", { name: "Séparer vers une nouvelle fiche" })).toBeDisabled();
    expect(within(choix).getByText(/garder au moins un résultat/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- components/athletes/AthleteDetachAction.test.tsx`
Expected: FAIL, module `./AthleteDetachAction` introuvable.

- [ ] **Step 3: Implement**

`frontend/lib/api/client.ts`, après `mergeAthletes` :

```ts
  /** Sépare des résultats vers une nouvelle fiche d'homonyme ; rend cette fiche (#1209). */
  detachParticipations: (athleteId: number, participationIds: number[]) =>
    request<AdminAthlete>(`/admin/athletes/${athleteId}/detach`, {
      method: "POST",
      body: JSON.stringify({ participation_ids: participationIds }),
    }),
```

`frontend/lib/queries/admin.ts`, après `useReassignParticipation` :

```ts
/**
 * Séparer une fiche (#1209) : mêmes écrans que le rattachement, plus la revue
 * d'identité, d'où un cas peut sortir.
 */
export function useDetachParticipations() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ athleteId, participationIds }: { athleteId: number; participationIds: number[] }) =>
      apiClient.detachParticipations(athleteId, participationIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.resultatsPublics });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.coureurs });
      qc.invalidateQueries({ queryKey: queryKeys.identityReview() });
    },
  });
}
```

`frontend/components/athletes/AthleteDetachAction.tsx` :

```tsx
"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button, Modal } from "@/components/tcn";
import { DangerConfirm } from "@/components/admin/DangerConfirm";
import { useDetachParticipations } from "@/lib/queries/admin";
import { useHydratedSession } from "@/lib/queries/auth";
import type { Participation } from "@/lib/types";
import { formatDate } from "@/lib/utils/date";

/**
 * « Séparer des résultats » : plusieurs personnes du même nom partagent la fiche
 * (#1209). Les résultats cochés partent sur une nouvelle fiche d'homonyme, que la
 * page ouvre ensuite.
 *
 * `DangerConfirm` déclaratif et non `useDangerConfirm` : la fiche athlète est
 * publique, hors de tout `DangerConfirmProvider` (patron de `CourseSourcesPanel`).
 * Deux pouvoirs, comme la route ; sans eux, rien n'est rendu.
 */
export function AthleteDetachAction({
  athleteId,
  athleteName,
  participations,
}: {
  athleteId: number;
  athleteName: string;
  participations: Participation[];
}) {
  const session = useHydratedSession();
  const pouvoirs = session.data?.permissions ?? [];
  const autorise = pouvoirs.includes("athletes:write") && pouvoirs.includes("participations:reassign");
  const [ouvert, setOuvert] = useState(false);
  const [coches, setCoches] = useState<Set<number>>(new Set());
  const [confirmation, setConfirmation] = useState(false);
  const declencheur = useRef<HTMLButtonElement>(null);
  const separation = useDetachParticipations();
  const router = useRouter();

  if (!autorise || participations.length < 2) return null;

  const nombre = coches.size;
  const ficheVidee = nombre === participations.length;
  const envoiPossible = nombre > 0 && !ficheVidee;
  const libelle = `${nombre} résultat${nombre > 1 ? "s" : ""}`;

  function basculer(id: number) {
    setCoches((avant) => {
      const apres = new Set(avant);
      if (apres.has(id)) apres.delete(id);
      else apres.add(id);
      return apres;
    });
  }

  function fermer() {
    setOuvert(false);
    setCoches(new Set());
  }

  async function separer() {
    try {
      const nouvelle = await separation.mutateAsync({ athleteId, participationIds: [...coches] });
      toast.success(`${libelle} séparé${nombre > 1 ? "s" : ""} vers une nouvelle fiche.`);
      setConfirmation(false);
      fermer();
      router.push(`/athletes/${nouvelle.id}`);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <>
      <Button
        ref={declencheur}
        variant="secondary"
        size="sm"
        onClick={() => setOuvert(true)}
        aria-label={`Séparer des résultats de ${athleteName}`}
      >
        Séparer des résultats
      </Button>

      {ouvert && !confirmation && (
        <Modal
          eyebrow="Fiche athlète"
          title="Séparer des résultats"
          onClose={fermer}
          footer={
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <Button variant="ghost" onClick={fermer}>
                Annuler
              </Button>
              <Button variant="primary" disabled={!envoiPossible} onClick={() => setConfirmation(true)}>
                Séparer vers une nouvelle fiche
              </Button>
            </div>
          }
        >
          <p style={{ margin: "0 0 12px", fontSize: 14, color: "var(--tcn-text-muted)" }}>
            Cochez les résultats d&apos;une autre personne nommée {athleteName}. Ils partiront sur une
            nouvelle fiche, distincte de celle-ci.
          </p>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {participations.map((p) => (
              <li key={p.id}>
                <label style={{ display: "flex", gap: 10, alignItems: "baseline", fontSize: 14, minHeight: 44 }}>
                  <input type="checkbox" checked={coches.has(p.id)} onChange={() => basculer(p.id)} />
                  <span>
                    {p.course.name}
                    <span style={{ color: "var(--tcn-text-faint)" }}>
                      {" · "}
                      {formatDate(p.course.event_date)}
                      {" · "}
                      {p.club ?? "Sans club"}
                    </span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {ficheVidee && (
            <p role="status" style={{ margin: "12px 0 0", fontSize: 13, color: "var(--tcn-text-muted)" }}>
              La fiche doit garder au moins un résultat.
            </p>
          )}
        </Modal>
      )}

      <DangerConfirm
        open={confirmation}
        onOpenChange={(ouverte) => !ouverte && setConfirmation(false)}
        titre={`Séparer ${libelle} vers une nouvelle fiche ?`}
        description={`Une nouvelle fiche ${athleteName} est créée avec ces résultats. Les deux fiches sont jugées distinctes et ne seront plus proposées à la fusion.`}
        libelleAction="Séparer"
        enAttente={separation.isPending}
        onConfirm={separer}
        finalFocus={declencheur}
      />
    </>
  );
}
```

Si le `Button` de `@/components/tcn` n'accepte pas `size="sm"` ou `variant="primary"`, reprendre les variantes utilisées par `AthleteMergeAction` et `ParticipationAdminActions`.

`frontend/app/(public_restricted)/athletes/[id]/EventsTable.tsx` : importer `AthleteDetachAction` et remplacer le bloc d'en-tête (l.241-244) par :

```tsx
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "20px 26px 16px", flexWrap: "wrap", gap: 8 }}>
        <h2 style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, fontWeight: 400, color: "var(--tcn-ink)", margin: 0 }}>Toutes les épreuves</h2>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <AthleteDetachAction athleteId={athleteId} athleteName={athleteName} participations={participations} />
          <div style={{ fontSize: 13, color: "var(--tcn-text-faint)", fontWeight: 600 }}>Sélectionnez une épreuve pour voir le détail →</div>
        </div>
      </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- components/athletes/AthleteDetachAction.test.tsx "app/(public_restricted)/athletes/[id]"`
Expected: PASS (les tests existants d'`EventsTable` et de la page restent verts : sans session, le bouton n'est pas rendu). Puis `cd frontend && npm run lint`.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add frontend/lib/api/client.ts frontend/lib/queries/admin.ts frontend/components/athletes/AthleteDetachAction.tsx frontend/components/athletes/AthleteDetachAction.test.tsx "frontend/app/(public_restricted)/athletes/[id]/EventsTable.tsx"
/usr/bin/git commit -m "feat(frontend): detach results of a shared athlete record (#1209)"
```

---

### Task E10: Front : cas `multi_club` dans `/admin/identites`

**Files:**
- Modify: `frontend/lib/types.ts` (`IdentityReviewReason`, `IdentityReviewCandidate`, nouveaux types)
- Modify: `frontend/lib/api/client.ts` (après `ignoreIdentityPair`)
- Modify: `frontend/lib/queries/admin.ts` (après `useIgnoreIdentityPair`)
- Modify: `frontend/components/admin/AthleteIdentityReviewTable.tsx`
- Test: `frontend/components/admin/AthleteIdentityReviewTable.test.tsx`

**Interfaces:**
- Consumes: `clubs` du candidat (E6), `POST /admin/identity-review/confirm-club` (E7).
- Produces: `apiClient.confirmIdentityClub(athleteId: number, clubKey: string) => Promise<IdentityClubConfirmResult>` ; `useConfirmIdentityClub()`.

- [ ] **Step 1: Write the failing test**

Dans `AthleteIdentityReviewTable.test.tsx` : ajouter `confirmIdentityClub` aux `vi.hoisted` et au mock d'`apiClient`, ajouter `clubs: []` aux deux cas de `CAS`, puis :

```tsx
const MULTI: IdentityReviewList = {
  candidates: [
    {
      reason: "multi_club",
      reason_label: "Plusieurs clubs sur une même fiche",
      athletes: [FICHE(37, "MARTIN", "Thomas", { club: "Triathlon Club Nantais", participations: 17 })],
      conflicts: [],
      clubs: [{ club: "Vendôme Triathlon", club_key: "vendometriathlon", results: 6 }],
    },
  ],
};

it("un cas multi-club liste ses clubs et confirme l'un d'eux", async () => {
  getSession.mockResolvedValue(session(["athletes:write", "athletes:read"]));
  listIdentityReview.mockResolvedValue(MULTI);
  confirmIdentityClub.mockResolvedValue({ athlete_id: 37, club_key: "vendometriathlon", confirmed_at: "2026-10-06T10:00:00Z" });
  afficher();

  const [carte] = await screen.findAllByRole("article");
  expect(within(carte).getByText(/Vendôme Triathlon · 6 résultats/)).toBeInTheDocument();
  expect(within(carte).getByText(/séparez/i)).toBeInTheDocument();
  await userEvent.click(within(carte).getByRole("button", { name: "Confirmer Vendôme Triathlon pour MARTIN Thomas" }));
  await confirmerDansLeDialog("Confirmer");

  expect(confirmIdentityClub).toHaveBeenCalledWith(37, "vendometriathlon");
  expect(toastSuccess).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- components/admin/AthleteIdentityReviewTable.test.tsx`
Expected: FAIL (texte des clubs et bouton absents ; erreur de type sur `clubs`).

- [ ] **Step 3: Implement**

`frontend/lib/types.ts` :

```ts
export type IdentityReviewReason =
  | "same_course_bibs"
  | "multi_club"
  | "club_homonym"
  | "swapped"
  | "concatenated"
  | "alias_collision";

/** Un club à vérifier sur une fiche (`multi_club`, #1209). */
export interface IdentityReviewClub {
  club: string;
  club_key: string;
  results: number;
}
```

ajouter `clubs: IdentityReviewClub[];` à `IdentityReviewCandidate` (commentaire : « vide hors `multi_club` »), et :

```ts
export interface IdentityClubConfirmResult {
  athlete_id: number;
  club_key: string;
  confirmed_at: string;
}
```

`frontend/lib/api/client.ts`, après `ignoreIdentityPair` (importer le type) :

```ts
  confirmIdentityClub: (athleteId: number, clubKey: string) =>
    request<IdentityClubConfirmResult>("/admin/identity-review/confirm-club", {
      method: "POST",
      body: JSON.stringify({ athlete_id: athleteId, club_key: clubKey }),
    }),
```

`frontend/lib/queries/admin.ts`, après `useIgnoreIdentityPair` :

```ts
export function useConfirmIdentityClub() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ athleteId, clubKey }: { athleteId: number; clubKey: string }) =>
      apiClient.confirmIdentityClub(athleteId, clubKey),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.identityReview() });
    },
  });
}
```

`frontend/components/admin/AthleteIdentityReviewTable.tsx` :

1. Importer `useConfirmIdentityClub` et le type `IdentityReviewClub`.
2. Nouveau composant, après `Conflits` :

```tsx
function ClubsAVerifier({ candidate }: { candidate: IdentityReviewCandidate }) {
  const confirmerClub = useConfirmIdentityClub();
  const confirmer = useDangerConfirm();
  const [fiche] = candidate.athletes;
  if (candidate.clubs.length === 0) return null;

  /** Geste neutre (#499) : aucun résultat ne bouge, le club ne sera plus signalé. */
  async function confirmerLeClub(club: IdentityReviewClub) {
    if (
      !(await confirmer({
        titre: `Confirmer « ${club.club} » pour ${nomDe(fiche)} ?`,
        description:
          "Ce club est bien celui de cette personne : il ne sera plus signalé, et ses prochains résultats sous ce club resteront sur cette fiche.",
        libelleAction: "Confirmer",
        actionNeutre: true,
      }))
    ) {
      return;
    }
    try {
      await confirmerClub.mutateAsync({ athleteId: fiche.id, clubKey: club.club_key });
      toast.success("Club confirmé : il ne sera plus signalé pour cette fiche.");
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Clubs à vérifier</p>
      <ul className="space-y-2">
        {candidate.clubs.map((club) => (
          <li key={club.club_key} className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span>
              {club.club} · {motCompte(club.results, "résultat")}
            </span>
            <Button
              size="sm"
              variant="outline"
              className="min-h-11"
              onClick={() => confirmerLeClub(club)}
              disabled={confirmerClub.isPending}
              aria-label={`Confirmer ${club.club} pour ${nomDe(fiche)}`}
            >
              Confirmer ce club
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

3. Dans `CarteCas`, après `<Conflits candidate={candidate} />`, rendre `<ClubsAVerifier candidate={candidate} />`, et remplacer le paragraphe `!paire` par :

```tsx
          {!paire && (
            <p className="text-[var(--tcn-text-faint)] text-xs">
              {candidate.reason === "multi_club"
                ? "Plusieurs personnes peuvent partager cette fiche : ouvrez-la et séparez les résultats de l'autre athlète, ou confirmez les clubs qui sont bien les siens."
                : "Deux personnes partagent cette fiche : ouvrez-la et réattribuez les résultats de l'autre athlète à sa propre fiche."}
            </p>
          )}
```

4. Docstring d'`AthleteIdentityReviewTable` : mentionner les fiches de membre à plusieurs clubs, qui se règlent par séparation ou par confirmation du club.

`motCompte(6, "résultat")` doit rendre « 6 résultats » ; vérifier dans `lib/utils/format.ts`, sinon aligner l'assertion du test sur sa sortie.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- components/admin/AthleteIdentityReviewTable.test.tsx`
Expected: PASS. Puis `cd frontend && npx tsc --noEmit` et `npm run lint`.

- [ ] **Step 5: Commit**

```bash
/usr/bin/git add frontend/lib/types.ts frontend/lib/api/client.ts frontend/lib/queries/admin.ts frontend/components/admin/AthleteIdentityReviewTable.tsx frontend/components/admin/AthleteIdentityReviewTable.test.tsx
/usr/bin/git commit -m "feat(frontend): review and confirm clubs of multi-club athlete records (#1209)"
```

# Weekend digest (#1363) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a `weekend-digest` CLI command, run by the Monday cron, that posts the club's results from the previous Saturday and Sunday to a dedicated Slack webhook.

**Architecture:** thin CLI (`app/cli/commands/weekend_digest.py`) → service `app/services/weekend_digest.py` (computes the weekend, collects, renders, sends) → `course_repository.list_all` (existing) + a new `participation_repository.weekend_digest_rows`. The send goes through `app.core.http.client` (anti-SSRF), and tests inject `httpx.MockTransport`.

**Tech Stack:** Python 3.13, Typer, SQLAlchemy 2.0 sync, httpx, pytest, GitHub Actions.

**Spec:** issue #1363 plus the design approved in chat on 2026-10-21, summarised here:
- Weekend = the Saturday and Sunday before `--date` (default: today, UTC). `--dry-run` prints the message without sending it.
- One line per course in the weekend that has at least one validated TCN (`club_only`). Each line shows the course name, linked to `<AUTH_REDIRECT_BASE_URL>/courses/<id>` (no link when that setting is empty), and the number of TCN classified (status `finisher` and `rank_overall` not null).
- Podiums: TCN placed 1 to 3 in the overall, gender (M/F only) or category ranking, shown with their best rank (the `club_service` rule).
- Names cited **never** include anonymised records (opposition #1172, `Anonyme …` name with an empty first name) or youths (`is_youth`). The counts still include them.
- Setting `SLACK_DIGEST_WEBHOOK_URL` (`SecretStr`, empty by default): when it is absent, log a warning and exit 0 without touching the database.
- **Empty weekend: nothing is posted**, an info line is logged, exit 0 (user's decision).
- Slack failure (HTTP error or status ≥ 400): exit 1, so the scheduled run turns red and `notify-failure` fires.
- A schedule-only step in `.github/workflows/batch.yml` that does not block the other steps. Secrets: `SLACK_DIGEST_WEBHOOK_URL` and `AUTH_REDIRECT_BASE_URL` in the `batch-production` environment, set later by the user.

## Global Constraints

- Language: French for user-facing text (Slack message, CLI messages, product docs, comments on business rules); English for identifiers, tests and technical logs.
- Layers `cli → services → repositories`: only repositories query the Session (`tests/test_layering.py`, `tests/test_service_boundaries.py`).
- No bare `httpx` in `app/`: always `app.core.http.client(transport=transport)` (`tests/test_core_http.py`).
- Unit tests without network: inject `httpx.MockTransport` and stub DNS with `monkeypatch.setattr(http, "_resolve", lambda host, port: ["93.184.216.34"])`.
- Never use a dash to punctuate a sentence (comments, docs, copy). Comment only the why.
- Run the commands from `backend/`. Unit tests: `uv run pytest -m "not integration"`, lint: `uv run ruff check .`.
- Conventional Commits, no `Co-Authored-By` trailer.

## Review Focus

1. Slack markup in names: a `&`, `<` or `>` in a course or athlete name breaks the `<url|label>` link. Escape them as `&amp;`, `&lt;`, `&gt;` (test in Task 1).
2. A TCN youth on the podium in the category ranking: they are omitted from the podiums but counted among the classified (test in Task 1).
3. A gender podium for an athlete with gender `X` or empty is not a podium (`is_gender_podium`). Without that check, an unknown gender would produce a false podium (test in Task 1).
4. Running on a Sunday or Saturday (manual replay): the weekend is the **previous** one, never the current one (test in Task 1).
5. A result pending validation, or a course whose TCN results are all pending: absent from the digest (filter `validated_clause` plus `hide_pending_only=True`, test in Task 1).

---

### Task 1: Collect and render the digest

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (new function, next to `club_podiums`)
- Modify: `backend/app/services/opposition_service.py` (make `is_anonymous` public)
- Modify: `backend/app/services/result_claims.py:91-93` (drop `_is_anonymous`, call `opposition_service.is_anonymous`)
- Modify: `backend/app/services/club_service.py:37` (rename `_best` to `best_rank`, update its callers in the file)
- Create: `backend/app/services/weekend_digest.py`
- Test: `backend/tests/test_services/test_weekend_digest.py`

**Interfaces:**
- Produces:
  - `participation_repository.weekend_digest_rows(db: Session, course_ids: list[int]) -> list[Row]`. Columns, in order: `Participation.course_id, Participation.status, Participation.rank_overall, Participation.rank_gender, Participation.rank_category, Participation.category, Athlete.prenom, Athlete.nom, Athlete.gender`. Filters: `course_id IN course_ids`, `validated_clause(...)`, `counts_for_tcn IS TRUE`. Empty list → `[]` with no query.
  - `opposition_service.is_anonymous(prenom: str | None, nom: str) -> bool`, which keeps the current rule: `not prenom and nom.startswith("Anonyme ")`.
  - `club_service.best_rank(ranks: dict[str, int | None]) -> tuple[str, int] | None`, the former `_best` with unchanged behaviour.
  - In `weekend_digest`:
    - `weekend_before(day: date) -> tuple[date, date]` returns (Saturday, Sunday).
    - `@dataclass(frozen=True) DigestPodium(name: str, rank: int, scope: str)`, where `scope` is in `("overall", "gender", "category")`.
    - `@dataclass(frozen=True) DigestCourse(course_id: int, name: str, finishers: int, podiums: list[DigestPodium])`.
    - `collect(db: Session, saturday: date, sunday: date) -> list[DigestCourse]`.
    - `render(courses: list[DigestCourse], *, saturday: date, sunday: date, base_url: str) -> str`.

- [ ] **Step 1: Write the failing tests** in `tests/test_services/test_weekend_digest.py`. Build the data like `tests/test_services/test_club_service.py`: `course_repository.get_or_create`, `athlete_repository.get_or_create(club="TCN")`, `participation_repository.create(club="TCN", ...)`, then `db_session.flush()`.
  - `test_weekend_before_a_monday_is_the_weekend_just_ended`: `weekend_before(date(2026, 10, 19)) == (date(2026, 10, 17), date(2026, 10, 18))`.
  - `test_weekend_before_a_sunday_or_saturday_is_the_previous_one`: Sunday 18/10 and Saturday 17/10 both give `(date(2026, 10, 10), date(2026, 10, 11))`.
  - `test_collect_counts_classified_tcn_and_their_podiums`: course on 17/10 with Alice (finisher, rank_overall=2), Bea (finisher, rank_overall=10, rank_category=1), Carl (`DNF`, rank_overall None). Expect one `DigestCourse` with `finishers == 2` and podiums `[DigestPodium("Alice …", 2, "overall"), DigestPodium("Bea …", 1, "category")]`, ordered by rank then name.
  - `test_collect_ignores_courses_outside_the_weekend`: a course on 16/10 (Friday) and one on 19/10 → `collect(...) == []`.
  - `test_collect_returns_nothing_for_an_empty_weekend`: empty database → `[]`.
  - `test_opposed_athletes_and_youths_are_never_named`: an anonymised athlete (`nom="Anonyme 12-34", prenom=""`, rank_overall=1) and a youth (category `"MIH"`, rank_category=1), both finishers. They are absent from `podiums`, but `finishers == 2`.
  - `test_a_gender_podium_needs_a_known_gender`: an athlete with gender `None`, rank_gender=1 and nothing else → no podium.
  - `test_pending_results_are_left_out`: the only TCN result is `is_pending_validation=True` → `[]`.
  - `test_render_lists_each_course_with_its_link_and_podiums`: `render([DigestCourse(12, "Tri & Co", 3, [DigestPodium("Alice Martin", 1, "overall")])], saturday=date(2026,10,17), sunday=date(2026,10,18), base_url="https://tcn.example")`. The result contains `"17/10 et 18/10/2026"`, `"<https://tcn.example/courses/12|Tri &amp; Co>"`, `"3 TCN classés"` and `"🥇 Alice Martin (scratch)"`.
  - `test_render_without_base_url_shows_the_name_without_link`: `base_url=""` → contains `"Tri &amp; Co"` but no `"<"`. With `finishers=1`, the text reads `"1 TCN classé"`.

- [ ] **Step 2: Run the tests and check they fail**
  Run: `uv run pytest tests/test_services/test_weekend_digest.py -n 0`
  Expected: FAIL on `ImportError` (module `app.services.weekend_digest` missing).

- [ ] **Step 3: Implement**
  - The repository function and the two promotions (`is_anonymous`, `best_rank`), per the Interfaces block.
  - `collect`: call `course_repository.list_all(db, club_only=True, date_from=saturday, date_to=sunday, page_size=500, hide_pending_only=True)`, then `weekend_digest_rows` on those ids. Ordering follows `list_all`.
    - A finisher is a row with `status.lower() == STATUS_FINISHER` (`app.scrapers.base`) and `rank_overall is not None`.
    - The podium is `best_rank({"overall": ro, "gender": rg if is_gender_podium(rg, gender) else None, "category": rc})`.
    - A name is cited only if `not is_anonymous(prenom, nom)` and `not is_youth(course.name, category, event_year=course.event_date.year)`.
    - The name is `f"{prenom} {nom}".strip()`.
  - `render`:
    - Header: `*Résultats TCN du week-end des {sat:%d/%m} et {sun:%d/%m/%Y}*`.
    - Course line: `• <url|name> : N TCN classé(s)`.
    - Podium line: indented, medals `🥇🥈🥉` indexed by rank, scope labels `{"overall": "scratch", "gender": "classement par sexe", "category": "catégorie"}`.
    - Escape `&`, `<`, `>` in every interpolated name.

- [ ] **Step 4: Run the tests and check they pass**
  Run: `uv run pytest tests/test_services/test_weekend_digest.py tests/test_services/test_club_service.py tests/test_services/test_result_claims.py -n 0`
  Expected: PASS. If `test_result_claims.py` does not exist, use `uv run pytest -k "claim or club_service"` instead.

- [ ] **Step 5: Commit**
  `git add` the files above, then `git commit -m "feat(digest): collect and render the club's weekend results (#1363)"`

### Task 2: Setting, Slack send and CLI command

**Files:**
- Modify: `backend/app/core/config.py` (next to `github_batch_token`)
- Modify: `backend/.env.example`
- Modify: `backend/app/services/weekend_digest.py`
- Create: `backend/app/cli/commands/weekend_digest.py`
- Modify: `backend/app/cli/__init__.py` (import + `app.command("weekend-digest")(weekend_digest)`)
- Test: `backend/tests/test_services/test_weekend_digest.py`, `backend/tests/test_cli/test_weekend_digest.py`

**Interfaces:**
- Consumes: `weekend_before`, `collect`, `render` (Task 1).
- Produces:
  - `Settings.slack_digest_webhook_url: SecretStr = SecretStr("")`. Its comment explains that the webhook is dedicated to the board, distinct from `SLACK_OPS_WEBHOOK_URL`, and that empty means a logged no-op.
  - `weekend_digest.build(db: Session, day: date, *, base_url: str) -> str | None`: `None` when the weekend is empty, otherwise `render(...)`.
  - `weekend_digest.DigestDeliveryError(Exception)`, with a French message that names the cause (status or network error, never the URL: it is a secret).
  - `weekend_digest.send(text: str, webhook_url: str, *, transport: httpx.BaseTransport | None = None) -> None`: `http.client(transport=transport)`, then `post(webhook_url, json={"text": text}, timeout=10)`. An `httpx.HTTPError` or a status ≥ 400 raises `DigestDeliveryError`.
  - CLI `weekend_digest(day: datetime | None = typer.Option(None, "--date", formats=["%Y-%m-%d"]), dry_run: bool = typer.Option(False, "--dry-run"))`.

- [ ] **Step 1: Write the failing tests**
  - Service, with the `_resolve` stub from the Global Constraints and a `_capture()` handler like `tests/test_services/test_batch_runs.py:40`:
    - `test_send_posts_the_text_as_json`: a single POST to the URL, with body `{"text": "x"}`.
    - `test_send_raises_on_a_slack_error`: the handler returns 404 → `DigestDeliveryError`.
    - `test_send_raises_on_a_network_error`: the handler raises `httpx.ConnectError` → `DigestDeliveryError`.
  - CLI, in `tests/test_cli/test_weekend_digest.py`, mirroring `test_entra_deletions.py`: `brancher_session(cmd)`, `CliRunner`, settings patched via `monkeypatch.setattr(cmd, "get_settings", lambda: Settings(...))` (or `get_settings.cache_clear()` plus env vars, whichever the module uses), and `cmd.weekend_digest_service.send` (or the name used for the import) replaced by a list that records calls:
    - `test_without_webhook_it_logs_and_exits_zero`: no webhook, `--date 2026-10-19` → exit 0, `send` not called, a warning in `caplog` that names `SLACK_DIGEST_WEBHOOK_URL`.
    - `test_an_empty_weekend_posts_nothing`: webhook set, empty database → exit 0, `send` not called.
    - `test_a_weekend_with_results_is_posted`: one TCN course on 17/10 → exit 0, `send` called once with a text that contains the course name.
    - `test_dry_run_prints_without_posting`: no webhook, `--dry-run`, one course → stdout contains the course name, `send` not called.
    - `test_a_delivery_failure_exits_one`: `send` raises `DigestDeliveryError` → exit 1.

- [ ] **Step 2: Run the tests and check they fail**
  Run: `uv run pytest tests/test_services/test_weekend_digest.py tests/test_cli/test_weekend_digest.py -n 0`
  Expected: FAIL (`send`, `build` and the command do not exist yet).

- [ ] **Step 3: Implement** the setting, `build`, `send` and the command. Order inside the command:
  1. Without `--dry-run`, if the webhook is empty: `logger.warning` and return. The database is not opened.
  2. `with session_scope() as db: text = build(db, day or utcnow().date(), base_url=settings.auth_redirect_base_url)`.
  3. If `text is None`: `logger.info("Aucune épreuve TCN le week-end du …, rien n'est envoyé.")` and return.
  4. With `--dry-run`: `typer.echo(text)` and return.
  5. Otherwise `send(...)`. On `DigestDeliveryError`: `logger.error` and `raise typer.Exit(1)`. On success: `typer.echo("Récapitulatif du week-end envoyé sur Slack.")`.

  `.env.example`: an empty `SLACK_DIGEST_WEBHOOK_URL=` entry with a French comment (the board's webhook, read by the Monday cron only, empty means no send).

- [ ] **Step 4: Run the tests and check they pass**
  Run: `uv run pytest tests/test_services/test_weekend_digest.py tests/test_cli/test_weekend_digest.py tests/test_config.py tests/test_core_http.py tests/test_layering.py tests/test_service_boundaries.py -n 0`
  Expected: PASS.

- [ ] **Step 5: Commit**
  `git commit -m "feat(cli): add weekend-digest posting to SLACK_DIGEST_WEBHOOK_URL (#1363)"`

### Task 3: Monday cron and docs

**Files:**
- Modify: `.github/workflows/batch.yml` (new step after `Count pending Entra deletions`, before `Run batch`; header comment and `schedule` comment listing the weekly steps)
- Modify: `backend/tests/test_workflows.py`
- Modify: `backend/app/cli/AGENTS.md` (invocation line in the block at the top; the « planification hebdomadaire » paragraph; a short `## weekend-digest (#1363)` section: weekend window, exclusions, exit codes 0/1, empty weekend = nothing posted, `--dry-run`)
- Modify: `docs/ci-cd.md` (table of the `batch-production` environment around line 693: `SLACK_DIGEST_WEBHOOK_URL` and `AUTH_REDIRECT_BASE_URL`; section `### Passage hebdomadaire` around line 902: the new step)

**Interfaces:**
- Consumes: the `weekend-digest` command (Task 2).

- [ ] **Step 1: Write the failing test** `test_the_weekend_digest_runs_on_the_schedule_only` in `tests/test_workflows.py`, next to `test_the_weekly_purges_and_members_sync_are_still_scheduled`. For the step with `id: digest`, assert:
  - `"github.event_name == 'schedule'" in step["if"]`;
  - `"app.cli weekend-digest" in step["run"]`;
  - `step["env"]["SLACK_DIGEST_WEBHOOK_URL"] == "${{ secrets.SLACK_DIGEST_WEBHOOK_URL }}"`;
  - `"AUTH_REDIRECT_BASE_URL" in step["env"]`;
  - `"continue-on-error" not in step` (a Slack failure has to turn the run red).

- [ ] **Step 2: Run it and check it fails**
  Run: `uv run pytest tests/test_workflows.py -n 0`
  Expected: FAIL on `KeyError: 'digest'`.

- [ ] **Step 3: Add the step** `Post weekend digest` / `id: digest`:
  - Condition: `if: ${{ !cancelled() && github.event_name == 'schedule' }}`.
  - `env`: `DATABASE_URL`, `SLACK_DIGEST_WEBHOOK_URL` and `AUTH_REDIRECT_BASE_URL`, all from `secrets.*`.
  - Script: `uv run python -m app.cli weekend-digest`, with the same `set +e` / summary `## Récapitulatif du week-end` pattern as `Purge orphan athletes`.
  - A French comment: the board's webhook (#1363), a step that does not depend on the previous ones, and the limit that only courses already imported at 3 a.m. UTC are listed.

  Then write the docs listed under **Files**.

- [ ] **Step 4: Run the workflow tests and the whole suite**
  Run: `uv run pytest tests/test_workflows.py -n 0`, then `uv run pytest -m "not integration"` and `uv run ruff check .`.
  Expected: all green, ruff `All checks passed!`.

- [ ] **Step 5: Commit**
  `git commit -m "ci(batch): post the weekend digest from the Monday schedule (#1363)"`

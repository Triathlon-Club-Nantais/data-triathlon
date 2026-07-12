# CLI : progression en direct & découpage en services

**Date** : 2026-07-12
**Statut** : validé, à implémenter
**Périmètre** : `backend/app/cli.py`, `backend/app/services/`, `backend/tests/`

## Problème

`app/cli.py` (323 lignes) porte les commandes `import-sheet` et `rescrape-db`. Deux
défauts :

1. **Aucun retour pendant l'exécution.** Les boucles de `run_import_sheet` et
   `run_rescrape_db` sont muettes : sur un batch de plusieurs dizaines d'épreuves,
   rien ne s'affiche avant le rapport final. Impossible de savoir où en est la
   commande, ni si elle progresse ou si elle est bloquée.
2. **Quatre responsabilités dans un seul fichier** : parsing du Google Sheet,
   orchestration des batches, rendu des rapports, déclaration Typer. Le docstring
   du module affirme « CLI mince par-dessus les services : aucune logique de
   scraping ni d'accès DB direct » — c'est faux : `run_import_sheet` et
   `run_rescrape_db` *sont* de l'orchestration métier, logée au mauvais étage.

Le refactoring consiste largement à rendre vraie cette phrase.

## Constat qui structure la solution

`services/import_service.py` expose **déjà** `iter_import_event()`, un générateur
qui émet les phases d'un import :

```
{phase: scraping} → {phase: saving, progress, total, imported, skipped} → {phase: done}
                                                                        ↘ {phase: error, message}
```

C'est ce que consomme le SSE du frontend (`ImportProgress`). La CLI, elle, appelle
la variante muette `import_event()`. **La progression fine existe donc déjà ; la
CLI ne la branche simplement pas.** On la réutilise telle quelle : aucune ligne
d'`import_service` n'est modifiée, et CLI et SSE partagent la même source de vérité.

## Architecture cible

### `services/` — logique pure, sans Typer ni Rich

| Fichier | Contenu |
| --- | --- |
| `services/progress.py` | `ProgressReporter` (Protocol) + `NullReporter` |
| `services/sheet_source.py` | `download_csv`, `parse_sheet_csv`, `normalize_url`, `dedupe_links`, `is_supported` + les constantes `DEFAULT_SHEET_URL`, `LINK_HEADER`, `LINK_COLUMN_FALLBACK_INDEX` |
| `services/bulk_import_service.py` | `SheetOutcome` + `run_import_sheet(...)` |
| `services/rescrape_service.py` | `RescrapeOutcome` + `run_rescrape_db(...)` |

Les deux services d'orchestration consomment `import_service.iter_import_event()`
et notifient un reporter au fil de l'eau.

### Le contrat de progression

`services/progress.py` — les services ne dépendent que de ce Protocol, jamais de
la couche CLI :

```python
class ProgressReporter(Protocol):
    def batch_start(self, total: int) -> None: ...
    def item_start(self, index: int, label: str) -> None: ...
    def item_progress(self, done: int, total: int) -> None: ...   # intra-épreuve
    def item_done(self, imported: int, skipped: int, error: str | None) -> None: ...
    def batch_end(self) -> None: ...
```

`NullReporter` (no-op) est le **défaut** des services : ils restent testables sans
terminal, et rien ne s'affiche si personne ne demande de progression.

**Règle de libellé (`label`)** — le nom de la course n'est *pas* connu avant le
scrape et `iter_import_event()` ne le remonte pas. Donc :

- `rescrape-db` part de la DB : `label = f"{provider} · {course.name}"`.
- `import-sheet` ne dispose que de l'URL : `label = f"{provider} · {url}"` (URL
  tronquée à ~60 caractères à l'affichage).

Remonter le nom de la course dans les phases d'`iter_import_event()` toucherait le
SSE : hors périmètre.

C'est le même idiome que `scrapers/registry.py` (registre par Protocol), déjà en
place dans le projet. L'inversion de dépendance rend l'orchestration réutilisable :
brancher un jour un reporter SSE sur un endpoint admin d'import de masse ne
demandera aucune réécriture du service.

### `cli/` — Typer et présentation, rien d'autre

```
app/cli/
  __init__.py                 # le typer.Typer() et l'enregistrement des commandes
  __main__.py                 # préserve `python -m app.cli`
  commands/import_sheet.py    # options Typer, choix du reporter, délégation, affichage
  commands/rescrape_db.py     #   idem
  progress.py                 # RichReporter, PlainReporter, sélecteur TTY
  reports.py                  # render_sheet_report, render_rescrape_report, sortie --json
```

`app/cli.py` est **supprimé** au profit du package `app/cli/` (sinon Python voit
deux modules du même nom).

## Comportement de la progression

### En terminal (TTY) — `RichReporter`

Deux barres imbriquées, la seconde réinitialisée à chaque épreuve :

```
Épreuves  ━━━━━━━━━━━━━━━╸────────────  18/42  0:03:12
  klikego · Triathlon de Nantes 2025 · enregistrement  ━━━━━━╸──────  128/450
```

(en `import-sheet`, la seconde ligne affiche l'URL au lieu du nom — voir la règle
de libellé plus haut.)

En fin de commande, les barres cèdent la place au rapport final actuel, inchangé.

### Hors terminal (cron, redirection, CI) — `PlainReporter`

Une ligne par épreuve, sans code ANSI :

```
[18/42] klikego · https://www.klikego.com/resultats/… → 128 importés, 4 ignorés (12.4s)
[19/42] timepulse · https://www.timepulse.fr/… → ERREUR : timeout scrape (30.0s)
```

La phase `scraping` (la plus longue) émet en plus une ligne « … scraping en cours »
dans ce mode, pour qu'un log ne reste pas muet 60 s.

### Sélection

Sur `sys.stdout.isatty()`. Deux options nouvelles : `--no-progress` (silence total,
`NullReporter`) et `--plain` (force le mode ligne à ligne même en TTY).

## Gestion des erreurs

Inchangée sur le fond : une épreuve qui échoue incrémente `errors`, le batch
continue. Nuance technique à traiter : `iter_import_event()` **yield**
`{"phase": "error"}` au lieu de lever. Les services doivent donc gérer les deux
voies — phase `error` *et* exception réelle — et les faire converger vers
`item_done(error=...)`.

## Interruption (Ctrl-C)

Aujourd'hui : traceback, aucun bilan, travail effectué invisible. Cible : les
commandes interceptent `KeyboardInterrupt`, affichent le **rapport partiel** de ce
qui a déjà été importé (chaque épreuve étant commitée, ce travail est réellement
persisté) et sortent en **code 130**. Sur une commande qui tourne 40 minutes, cela
change tout.

## Tests

### Migration des 14 tests existants

`tests/test_cli.py` est scindé ; le contenu des tests ne change pas, seulement leur
adresse :

- 6 tests de parsing/normalisation → `tests/test_services/test_sheet_source.py`
- 4 tests de `run_import_sheet` → `tests/test_services/test_bulk_import_service.py`
- 4 tests de `run_rescrape_db` → `tests/test_services/test_rescrape_service.py`

### Tests nouveaux

Un `FakeReporter` enregistrant ses appels sert de sonde :

- `run_import_sheet` relaie bien les `item_progress` issus de `iter_import_event`
- l'ordre `batch_start → item_start* → batch_end` est respecté
- une épreuve en erreur produit `item_done(error=...)` sans interrompre le batch

À côté :

- `PlainReporter` n'émet aucun code ANSI
- le sélecteur choisit `PlainReporter` hors TTY
- un `KeyboardInterrupt` en milieu de batch produit le rapport partiel et le code 130
- smoke tests des commandes Typer via `typer.testing.CliRunner` (dry-run, `--json`)

Tous restent sans réseau (les scrapes sont monkeypatchés, comme aujourd'hui).

## Dépendances

Aucune installation nouvelle : `rich` (15.0.0) est **déjà présent**, tiré en
dépendance dure par `typer==0.26.7` (`Requires-Dist: rich>=13.8.0`, sans condition).
On l'ajoute simplement en explicite dans `requirements.txt` puisqu'on l'importe
désormais directement.

## Compatibilité

`python -m app.cli import-sheet …` et `rescrape-db` conservent exactement leurs
options et leur rapport final. Ajouts seuls : `--no-progress` et `--plain`.

## Hors périmètre (YAGNI)

- Pas de reprise après interruption (pas de reprise là où le batch s'est arrêté).
- Pas de reporter SSE : le Protocol le rend possible, on ne l'écrit pas maintenant.
- Pas de parallélisme entre épreuves : le `--delay` de politesse reste séquentiel
  et volontaire.

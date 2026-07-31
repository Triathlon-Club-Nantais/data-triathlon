# Contracts — Fan-out Klikego

**Feature** : 005-klikego-fanout — [plan.md](../plan.md)

Trois contrats fixent la surface exposée par la feature. Ils sont **stables** au sens du Principe IV et doivent être testés en TDD (Principe III).

## Contrat C1 — `klikego._enumerate_heats(html: str) -> list[tuple[str, str]]`

**Contexte** : nouveau helper, testé sur fixtures HTML sans réseau.

**Signature** :

```python
def _enumerate_heats(html: str) -> list[tuple[str, str]]:
    """Extrait les (slug, label) de <el-select name="heat">/<el-option>.

    Retourne la liste dans l'ordre du DOM (l'ordre de programme de Klikego).
    Renvoie [] si <el-select name="heat"> est absent (page non-classement).
    """
```

**Cas de test** (fixtures HTML) :

| Fixture | Attendu | Note |
|---------|---------|------|
| `mesquer-2026-event.html` | 8 tuples, `('triathlon-s-indiv', 'Triathlon S Indiv')` inclus | Cas nominal, base du fix #153 |
| `nozeen-2025-no-select.html` | `[]` | Page sans `<el-select>` |
| HTML vide `""` | `[]` | Robustesse |
| HTML sans `<el-option>` mais avec le `<el-select>` | `[]` | Rare mais possible |

## Contrat C2 — `klikego.scrape_event_all(event_id, heat, event_name, slug, *, cache_probe=None) -> tuple[list[ScrapedResult], FanoutTrace]`

**Modification** de la fonction existante. Signature **élargie** (retour = tuple, kwarg `cache_probe`).

**Signature** :

```python
def scrape_event_all(
    event_id: str, heat: str, event_name: str, slug: str,
    *, cache_probe: Callable[[str], bool] | None = None,
) -> tuple[list[ScrapedResult], FanoutTrace]:
    ...
```

**Nouveau comportement** :

1. Si `heat` est vide (chemin nominal du provider) : GET la page événement, `_enumerate_heats(html)`. Boucler sur chaque `(heat_slug, heat_label)` :
   - Construire `heat_url = f"{BASE}/resultats/{slug}/{event_id}?heat={heat_slug}"`.
   - Si `cache_probe(heat_url) is True` : incrémenter `trace.heats_cached`, ne pas scraper le heat.
   - Sinon scraper le heat via l'ancien code par heat, appender au `results`.
   - Sur exception au scrape : `trace.failures.append({"heat_slug": heat_slug, "reason": str(exc)})`, `logger.warning`, poursuivre.
2. Si `heat` est renseigné (mode `--single-heat`) : scraper ce seul heat, `trace = FanoutTrace(heats_enumerated=1, heats_cached=0, heats_imported=0, failures=[])` (ou 0/0/0/[{...}] si échec).
3. Si `_enumerate_heats` rend `[]` (page sans `<el-select>`) : retour `([], FanoutTrace(0, 0, 0, []))`, laisser `import_service._require_event_name` produire l'erreur nominale.
4. `heats_imported` est dérivé côté aval (`import_service`) via `heats_enumerated - heats_cached - len(failures)`. Le scraper le laisse à 0.

**Cas de test** (mockés httpx avec `HTTPTransport` custom pour rester offline, ou via monkeypatch de la fonction interne qui GET la page événement) :

| Cas | Attendu |
|-----|---------|
| Heat vide, page 8-heats, `cache_probe=None`, tous OK | 8 `ScrapedResult`, `trace = FanoutTrace(8, 0, 0, [])` |
| Heat vide, page 8-heats, `cache_probe` qui rend `True` pour 3 heats | 5 `ScrapedResult` (les non-cachés), `trace.heats_cached == 3`, `trace.failures == []` |
| Heat vide, page 8-heats, 1 heat lève dans son scrape | 7 `ScrapedResult`, `trace.failures == [{"heat_slug": …, "reason": …}]`, `logger.warning` capturé |
| Heat vide, page sans `<el-select>` | `([], FanoutTrace(0, 0, 0, []))` |
| Heat `"triathlon-s-indiv"`, page 8-heats | 1 `ScrapedResult` (mode single-heat), `trace.heats_enumerated == 1` |
| Heat vide, URL de l'événement porte `?heat=X` dans son query | `?heat=X` **ignoré** par `KlikegoProvider.scrape_event_all` (test au niveau provider), fan-out complet |

## Contrat C3 — CLI `rescrape-db --single-heat`

**Nouveau flag** de la commande existante.

**Signature Typer** :

```python
single_heat: bool = typer.Option(
    False, "--single-heat",
    help="N'importe que le heat désigné par le ?heat= de --url (aucun fan-out).",
)
```

**Règles de validation** (échec avant tout travail, code Click 2) :

| Combinaison | Comportement |
|-------------|--------------|
| `--single-heat` seul (pas de `--url`) | Erreur d'usage : « `--single-heat` exige `--url` avec un paramètre `?heat=` » |
| `--single-heat --url https://…?heat=X` (1 URL) | OK — X importé, pas de fan-out |
| `--single-heat --url A?heat=X --url B?heat=Y` (N URLs, toutes avec `?heat=`) | OK — chaque URL importée en single-heat |
| `--single-heat --url https://…` (URL nue) | Erreur d'usage : « `--single-heat` exige `?heat=` dans l'URL » |
| `--single-heat --provider klikego` | Erreur d'usage : incompatible avec les filtres de base (`--provider`, `--older-than`) |
| `--single-heat --urls-from …` | OK — chaque URL du fichier doit porter `?heat=`, sinon échec ciblé sur cette URL au moment de l'import |

**Rationale** : `--single-heat` doit être **explicite** et **borné** (Principe V — neutralité par défaut). Un flag global qui débraye le fan-out sur toutes les URLs d'un batch n'est pas voulu.

**Non-goal** : `--single-heat` n'est **pas** ajouté à `import-sheet` (l'import de masse doit rester nominal, le fan-out y est la valeur ajoutée).

**Bilan CLI enrichi** : `rescrape-db` et `import-sheet` exposent les mêmes 4 compteurs et la liste `failures` dans :

- le rapport texte (stderr en mode terminal, stdout en mode non-JSON) : nouveau bloc « Heats en erreur (détail) : » sous les compteurs, un par ligne (`{heat_slug}: {reason}`).
- la charge `--json` : clés `heats_enumerated`, `heats_imported`, `heats_cached`, `heats_failed`, `failures` au **niveau de chaque bilan d'épreuve**, plus les agrégats correspondants au niveau du bilan global du batch.

## Contrat C4 — SSE `POST /api/v1/scrape/import` (contrat étendu)

La phase `done` ajoute quatre compteurs et une liste, **rétro-compatibles** (un consommateur qui ignore les champs inconnus continue de fonctionner).

```json
{
  "phase": "done",
  "imported": 42,
  "updated": 3,
  "skipped": 0,
  "reconciled": 1,
  "reassignments": [],
  "total": 46,
  "courses": [
    { "id": 23, "name": "Mesquer Triathlon S", "event_type": "triathlon-s" },
    { "id": 24, "name": "Mesquer Swimrun M Duo", "event_type": "swimrun-m" }
  ],
  "heats_enumerated": 8,
  "heats_imported": 5,
  "heats_cached": 2,
  "heats_failed": 1,
  "failures": [
    { "heat_slug": "triathlon-xs-relais", "reason": "HTTPError 502 sur détail" }
  ]
}
```

**Invariants** :

- `heats_enumerated = heats_imported + heats_cached + heats_failed` (exhaustif, disjoint).
- `failures.length == heats_failed`.
- Sur import mono-heat : `heats_enumerated ∈ {0, 1}`, `failures = []` sauf si le heat unique lève, auquel cas la phase est `error`, pas `done`.
- Sur cache TTL frais (court-circuit `_cached_result`) : les 4 compteurs valent 0 (l'import n'a rien re-scrapé), `courses` porte la liste des courses en cache.

## Contrat C6 — `registry.get_provider(url) -> Provider | None`

**Nouvelle fonction** publique dans `backend/app/scrapers/registry.py`.

**Signature** :

```python
def get_provider(url: str) -> Provider | None:
    """Retourne l'instance de provider qui reconnaît l'URL, ou None si aucun."""
```

**Contrat** :

- Retourne le premier `Provider` de `PROVIDERS` dont `matches(url)` est vrai — même règle de dispatch que `scrape_event_all(url)` et `detect_provider(url)`.
- Retourne `None` si aucun provider ne matche (au lieu de lever).
- N'a **aucun effet de bord** — appelable plusieurs fois, réentrance-safe.

**Cas de test** dans `backend/tests/test_registry.py` :

| Cas | Attendu |
|-----|---------|
| URL Klikego | Instance de `KlikegoProvider` |
| URL Breizh Chrono | Instance de `BreizhChronoProvider` |
| URL `live.breizhchrono.com` | Instance de `BreizhChronoProvider` (host multi-façades) |
| URL inconnue (github.com) | `None` |
| URL malformée (`https://[oops`) | `None` — pas d'exception |

**Usage** : `import_service.iter_import_event` appelle `registry.get_provider(url)` **après** `_scrape_all` pour lire `provider.last_trace` (cf. contrat R3). C'est la seule voie prévue vers l'instance depuis le service — pas d'accès direct à `PROVIDERS`.

## Contrat C5 — Front `ImportProgress.tsx` (rendu additif)

**Modification** ciblée du composant existant. Aucune modification du hook `useImportStream`.

**Comportement à ajouter à la phase `done`** :

- Si `state.courses.length > 0` : afficher, sous le message actuel, une liste `<Link href={`/courses/${c.id}`}>{c.name} · {chip event_type}</Link>` pour chaque course.
- Rendu identique pour `N=1` : pas de branche « singleton vs pluriel » (le compteur `N courses importées :` peut se lire au singulier via une petite règle d'accord — pas de composant conditionnel).

**Cas de test Vitest** (fixtures `ImportState`) :

| État | Attendu au rendu |
|------|------------------|
| `state.phase = "done"`, `state.courses = []` | Message actuel sans liste (cas cache TTL frais qui rend `courses: []`) |
| `state.phase = "done"`, `state.courses = [1 elem]` | Message + 1 lien vers `/courses/<id>` |
| `state.phase = "done"`, `state.courses = [8 elems]` | Message + 8 liens, ordre stable |
| `state.phase = "error"` | Message d'erreur seul (inchangé) |

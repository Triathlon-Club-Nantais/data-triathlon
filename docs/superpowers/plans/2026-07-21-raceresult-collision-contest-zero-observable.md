# RaceResult — collision de dossard observable (repli `Contest="0"`) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre observable (log d'alerte) la collision silencieuse de dossard du repli `Contest="0"` de RaceResult, et épingler par tests le cas mixte non vérifié — sans changer le comportement.

**Architecture :** Un helper pur `_identites_incompatibles` dans `raceresult.py` détecte deux identités d'athlète distinctes ; la boucle de fusion de `scrape_event_all` émet un `logger.warning` avant que `_prefer` ne tranche (arbitrage inchangé). Des tests de caractérisation figent le comportement du cas mixte `Contest="0"`/`!="0"`.

**Tech Stack :** Python 3.13, pytest (marker `not integration`), `uv run` (depuis `backend/`), `caplog` pour les assertions de log.

## Global Constraints

- Langue : commentaires, docstrings et messages en **français** (avec accents). Cf. AGENTS.md.
- Tests **sans réseau** (marker par défaut `not integration`). Les tests de ce plan câblent des payloads en mémoire via l'helper existant `_monte_pipeline` / `_payload` de `test_raceresult.py`.
- Commits : Conventional Commits. Terminer chaque message par `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Comportement inchangé** : aucune modification de la clé de fusion, de `_prefer`, ni du nombre de `Course`/lignes retenues. On instrumente, on ne corrige pas.
- Toutes les commandes se lancent depuis `backend/`. Chemins de fichiers relatifs à la racine du dépôt.
- Le module cible est `backend/app/scrapers/raceresult.py`, la table d'accents existante `_ACCENTS` (ligne ~225), la boucle de fusion dans `scrape_event_all` (lignes ~1138-1152), le logger module `logger` (ligne 53).

---

### Task 1 : Helper `_identites_incompatibles` (fonction pure)

**Files:**
- Modify: `backend/app/scrapers/raceresult.py` (ajout du helper après `_prefer`, ~ligne 1064)
- Test: `backend/tests/test_raceresult.py` (nouveaux tests unitaires, à placer près des autres tests de helpers, ex. après `test_prefer_*` ~ligne 1560)

**Interfaces:**
- Consumes : `ScrapedResult` (de `.base`) ; ses attributs `athlete_name`, `athlete_firstname` (strings, éventuellement vides) ; la table `_ACCENTS` déjà définie dans le module.
- Produces : `_identites_incompatibles(a: ScrapedResult, b: ScrapedResult) -> bool` — `True` ssi `a` et `b` nomment **deux athlètes distincts** ; `False` si l'un des deux est anonyme (nom **et** prénom vides) ou si les identités coïncident après pliage casse+accents.

- [ ] **Step 1 : Écrire les tests unitaires (échouent)**

Ajouter dans `backend/tests/test_raceresult.py` :

```python
def _res(nom: str = "", prenom: str = "") -> raceresult.ScrapedResult:
    """ScrapedResult minimal pour éprouver la comparaison d'identités."""
    return raceresult.ScrapedResult(
        source_url="u", provider="raceresult", bib_number="7",
        athlete_name=nom, athlete_firstname=prenom,
    )


def test_identites_incompatibles_deux_noms_pleins_distincts():
    assert raceresult._identites_incompatibles(
        _res("DUPONT", "Jean"), _res("MARTIN", "Luc")
    ) is True


def test_identites_incompatibles_un_cote_anonyme_est_un_enrichissement():
    # Une liste sans patronyme : fusion d'enrichissement légitime, pas collision.
    assert raceresult._identites_incompatibles(
        _res("DUPONT", "Jean"), _res("", "")
    ) is False
    assert raceresult._identites_incompatibles(
        _res("", ""), _res("MARTIN", "Luc")
    ) is False


def test_identites_incompatibles_tolere_casse_et_accents():
    # « José » / « JOSE » : même personne, divergence de casse/accent seulement.
    assert raceresult._identites_incompatibles(
        _res("DUPONT", "José"), _res("dupont", "JOSE")
    ) is False


def test_identites_incompatibles_meme_identite_pleine():
    assert raceresult._identites_incompatibles(
        _res("DUPONT", "Jean"), _res("DUPONT", "Jean")
    ) is False
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run (depuis `backend/`) :
```bash
uv run pytest tests/test_raceresult.py -k identites_incompatibles -q
```
Expected : FAIL — `AttributeError: module ... has no attribute '_identites_incompatibles'`.

- [ ] **Step 3 : Implémenter le helper**

Insérer dans `backend/app/scrapers/raceresult.py` après la fonction `_prefer` (~ligne 1064) :

```python
def _identite_pliee(r: ScrapedResult) -> tuple[str, str]:
    """(nom, prénom) plié en minuscules et accents neutralisés, pour comparaison.

    Réutilise `_ACCENTS` afin qu'une divergence de seule casse ou de seul accent
    (« José » / « JOSE ») ne compte pas comme deux identités.
    """
    def plie(s: str) -> str:
        return (s or "").translate(_ACCENTS).strip().lower()

    return plie(r.athlete_name), plie(r.athlete_firstname)


def _identites_incompatibles(a: ScrapedResult, b: ScrapedResult) -> bool:
    """Vrai si `a` et `b` nomment deux athlètes **distincts**.

    Sert de garde à l'instrumentation de la collision de dossard du repli
    `Contest="0"` (issue #65, §13.19 du sondage) : sur une même clé de fusion,
    deux identités pleines et différentes signalent que `_prefer` s'apprête à
    écraser une personne au profit d'une autre — le « signal à guetter » que le
    sondage réclame.

    Rend **False** dès qu'un côté est anonyme (nom et prénom vides) : c'est le cas
    nominal d'une fusion d'enrichissement, où une liste sans patronyme complète
    une liste qui en porte un. Alerter là serait du bruit. La comparaison est
    tolérante à la casse et aux accents (cf. `_identite_pliee`).
    """
    ida, idb = _identite_pliee(a), _identite_pliee(b)
    if not any(ida) or not any(idb):
        return False
    return ida != idb
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run :
```bash
uv run pytest tests/test_raceresult.py -k identites_incompatibles -q
```
Expected : PASS (4 tests).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "feat(raceresult): helper _identites_incompatibles (garde de collision, #65)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2 : Émettre le warning de collision dans `scrape_event_all`

**Files:**
- Modify: `backend/app/scrapers/raceresult.py` (boucle de fusion de `scrape_event_all`, ~lignes 1147-1152)
- Test: `backend/tests/test_raceresult.py` (tests d'intégration en mémoire via `_monte_pipeline`, à placer après `test_scrape_event_all_groupe_zero_corrobore_qualifie_toujours` ~ligne 1850)

**Interfaces:**
- Consumes : `_identites_incompatibles` (Task 1) ; `logger` (module) ; dans la boucle : `event_id`, `libelle`, `r` (le `ScrapedResult` courant), `ancien`, `fusion`.
- Produces : un `logger.warning` par collision d'identités distinctes sur une clé déjà occupée. Aucun changement de la valeur retenue dans `fusion`.

- [ ] **Step 1 : Écrire les tests (échouent)**

Ajouter dans `backend/tests/test_raceresult.py` (juste après `test_scrape_event_all_groupe_zero_corrobore_qualifie_toujours`). Ces tests réutilisent `_monte_pipeline` / `_payload` déjà définis dans le fichier.

```python
def test_scrape_event_all_collision_didentite_dans_le_repli_alerte(monkeypatch, caplog):
    """§13.19 : repli `Contest="0"` non corroboré → une `Course` unique. Deux
    personnes distinctes au même dossard entrent en collision sur la clé
    `("", dossard)` ; `_prefer` en écrasera une. On veut un warning explicite —
    le comportement de fusion, lui, ne change pas.

    Groupe `Découverte` étranger à `contests` ({1: Distance S, 2: Distance M}) →
    repli sans qualifiant.
    """
    specs = [("Général", "0")]
    payloads = {("Général", "0"): _payload({
        "#1_Découverte": {"#1_": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]},
        "#2_Rando": {"#1_": [["7", "2", "Luc MARTIN", "ACL", "02:00:00"]]},
    })}
    _monte_pipeline(monkeypatch, specs, payloads)

    with caplog.at_level("WARNING", logger="app.scrapers.raceresult"):
        res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    # Comportement inchangé : repli → une seule Course, un seul dossard retenu.
    assert len(res) == 1
    assert {r.event_name for r in res} == {"Épreuve"}
    # Signal émis, mentionnant le dossard et les deux identités.
    collisions = [rec for rec in caplog.records if "collision" in rec.message.lower()]
    assert len(collisions) == 1
    msg = collisions[0].getMessage()
    assert "7" in msg
    assert "DUPONT" in msg and "MARTIN" in msg


def test_scrape_event_all_fusion_denrichissement_ne_declenche_aucune_alerte(monkeypatch, caplog):
    """Deux listes d'un même contest décrivant la **même** personne, l'une sans
    club : fusion d'enrichissement nominale. Aucun warning ne doit être émis."""
    specs = [("Maigre", "1"), ("Riche", "1")]
    payloads = {
        ("Maigre", "1"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "", "01:00:00"]]}}),
        ("Riche", "1"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]}}),
    }
    _monte_pipeline(monkeypatch, specs, payloads)

    with caplog.at_level("WARNING", logger="app.scrapers.raceresult"):
        res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert len(res) == 1 and res[0].club == "TCN"
    assert [rec for rec in caplog.records if "collision" in rec.message.lower()] == []
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run :
```bash
uv run pytest tests/test_raceresult.py -k "collision_didentite or denrichissement_ne_declenche" -q
```
Expected : FAIL sur `test_..._collision_..._alerte` — `assert len(collisions) == 1` échoue (0 collision, aucun warning émis). L'autre test passe déjà (négatif).

- [ ] **Step 3 : Instrumenter la boucle de fusion**

Dans `backend/app/scrapers/raceresult.py`, la boucle de fusion de `scrape_event_all` (~lignes 1147-1152) est actuellement :

```python
                    if not r.bib_number:
                        continue
                    cle = (libelle, r.bib_number)
                    ancien = fusion.get(cle)
                    if ancien is None or _prefer(r, ancien):
                        fusion[cle] = r
```

La remplacer par :

```python
                    if not r.bib_number:
                        continue
                    cle = (libelle, r.bib_number)
                    ancien = fusion.get(cle)
                    # §13.19 (issue #65) : sur le repli `Contest="0"` non
                    # corroboré, toutes les lignes partagent le qualifiant vide.
                    # Deux personnes distinctes au même dossard s'y écrasent alors
                    # sans trace via `_prefer`. On ne change pas l'arbitrage — le
                    # sondage établit que le compromis est le bon — mais on rend
                    # la collision **bruyante** : muette sur tout le panel réel,
                    # elle ne se déclenche que sur une forme non observée.
                    if ancien is not None and _identites_incompatibles(r, ancien):
                        logger.warning(
                            "RaceResult %s : dossard %s en collision sous le "
                            "qualifiant %r — deux identités distinctes "
                            "(%s %s / %s %s), une sera écrasée sans trace "
                            "(cf. #65 §13.19)",
                            event_id, r.bib_number, libelle or "(aucun)",
                            ancien.athlete_name, ancien.athlete_firstname,
                            r.athlete_name, r.athlete_firstname,
                        )
                    if ancien is None or _prefer(r, ancien):
                        fusion[cle] = r
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run :
```bash
uv run pytest tests/test_raceresult.py -k "collision_didentite or denrichissement_ne_declenche" -q
```
Expected : PASS (2 tests).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "feat(raceresult): alerter sur une collision d'identité de dossard (#65 §13.19)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3 : Tests de caractérisation du cas mixte `Contest="0"` + `Contest!="0"` (§13.17)

**Files:**
- Test: `backend/tests/test_raceresult.py` (après les tests de collision de la Task 2)

**Interfaces:**
- Consumes : `_monte_pipeline`, `_payload`, `raceresult.scrape_event_all`. Le `config` monté par `_monte_pipeline` porte `contests = {"1": "Distance S", "2": "Distance M"}` : un libellé de groupe « Découverte » y est donc **étranger**, et « Distance S »/« Distance M » y sont **corroborés**.
- Produces : aucun code de production. Fige le comportement actuel de la forme mixte (jamais rencontrée au panel) pour détecter toute dérive.

- [ ] **Step 1 : Écrire les tests de caractérisation (doivent passer d'emblée)**

Ces tests décrivent le comportement **actuel** : ils passent sans nouvelle modification de production. Ils échoueraient si un futur changement altérait la qualification mixte. Ajouter dans `backend/tests/test_raceresult.py` :

```python
def test_scrape_event_all_mixte_contest_zero_corrobore_et_explicite(monkeypatch):
    """§13.17 — forme mixte non rencontrée au panel, comportement épinglé.

    Une liste `Contest="2"` (explicite → `Distance M`) coexiste avec une liste
    `Contest="0"` dont le groupe `Distance S` est corroboré par `contests`. Les
    deux voies qualifient : deux `Course` distinctes, dossards non mêlés.
    """
    specs = [("Explicite", "2"), ("Général", "0")]
    payloads = {
        ("Explicite", "2"): _payload({"#1_Distance M": {"#1_": [["8", "2", "Luc MARTIN", "TCN", "02:00:00"]]}}),
        ("Général", "0"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]}}),
    }
    _monte_pipeline(monkeypatch, specs, payloads)

    res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert {r.event_name for r in res} == {"Épreuve - Distance S", "Épreuve - Distance M"}


def test_scrape_event_all_mixte_contest_zero_etranger_se_replie(monkeypatch, caplog):
    """§13.17 / §13.19 — forme mixte avec libellé `Contest="0"` **étranger**.

    La voie `Contest="1"` reste qualifiée (`Distance S`). La voie `Contest="0"`,
    dont le groupe `Découverte` est absent de `contests`, se replie sur le nom
    d'épreuve nu. Un dossard partagé entre les deux voies produit donc **deux
    `Course` distinctes** (clés de fusion `("Distance S", …)` et `("", …)`),
    sans collision : comportement épinglé **tel quel**, c'est l'état non vérifié
    que #65 documente.
    """
    specs = [("Explicite", "1"), ("Général", "0")]
    payloads = {
        ("Explicite", "1"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]}}),
        ("Général", "0"): _payload({"#1_Découverte": {"#1_": [["7", "9", "Jean DUPONT", "TCN", "00:30:00"]]}}),
    }
    _monte_pipeline(monkeypatch, specs, payloads)

    with caplog.at_level("WARNING", logger="app.scrapers.raceresult"):
        res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    # Deux Course : le dossard partagé ne collisionne pas (qualifiants distincts).
    assert len(res) == 2
    assert {r.event_name for r in res} == {"Épreuve - Distance S", "Épreuve"}
    # Même personne des deux côtés : aucune alerte de collision d'identité.
    assert [rec for rec in caplog.records if "collision" in rec.message.lower()] == []
```

- [ ] **Step 2 : Lancer les tests, vérifier le succès (caractérisation)**

Run :
```bash
uv run pytest tests/test_raceresult.py -k "mixte_contest_zero" -q
```
Expected : PASS (2 tests). S'ils échouent, la qualification mixte a dérivé — investiguer avant de forcer.

- [ ] **Step 3 : Commit**

```bash
git add backend/tests/test_raceresult.py
git commit -m "test(raceresult): épingler le cas mixte Contest=0/!=0 (#65 §13.17)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4 : Note de clôture dans le sondage d'API (§13.17 et §13.19)

**Files:**
- Modify: `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` (points 17 et 19 de la §13, ~lignes 684-711)

**Interfaces:**
- Consumes : rien (documentation).
- Produces : renvoi explicite vers #65 précisant que l'angle mort est désormais **observable** (pas fermé) et que le cas mixte est épinglé par test.

- [ ] **Step 1 : Ajouter la note au point 17 (§13.17)**

Dans `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`, à la fin du point 17 (juste avant le point 18), ajouter un paragraphe :

```markdown

    **Suivi #65** : cette forme mixte est désormais **épinglée par des tests de
    caractérisation** (`test_scrape_event_all_mixte_contest_zero_*`), qui figent
    le comportement actuel — voie `!="0"` qualifiée, voie `"0"` corroborée ou
    repliée sur le nom nu. Ils détecteront toute dérive future ; ils ne
    **valident** rien, faute d'épreuve réelle.
```

- [ ] **Step 2 : Ajouter la note au point 19 (§13.19)**

À la fin du point 19 (après le paragraphe « Signal à guetter… »), ajouter :

```markdown

    **Suivi #65** : ce signal est désormais **émis** — `scrape_event_all` loggue
    un `warning` quand une clé de fusion écrase deux identités d'athlète
    distinctes (`_identites_incompatibles`). L'angle mort est rendu **observable**,
    pas fermé : le comportement de fusion reste inchangé (le compromis du §3.1
    reste le bon). Muet sur tout le panel réel, le signal ne se déclenche que sur
    la forme non observée décrite ici.
```

- [ ] **Step 3 : Vérifier la cohérence du document**

Run :
```bash
grep -n "Suivi #65" docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md
```
Expected : deux occurrences (points 17 et 19).

- [ ] **Step 4 : Commit**

```bash
git add docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md
git commit -m "docs(raceresult): clôturer les angles morts §13.17/§13.19 du sondage (#65)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5 : Vérification finale de non-régression

**Files:** aucun (vérification).

**Interfaces:**
- Consumes : l'ensemble des changements des Tasks 1-4.
- Produces : preuve que la suite backend reste verte et qu'aucun warning parasite n'apparaît sur les fixtures existantes.

- [ ] **Step 1 : Lancer toute la suite RaceResult**

Run (depuis `backend/`) :
```bash
uv run pytest tests/test_raceresult.py -q
```
Expected : PASS, incluant les nouveaux tests (helper, collision, mixte).

- [ ] **Step 2 : Lancer la suite unitaire complète**

Run :
```bash
uv run pytest -m "not integration" -q
```
Expected : PASS. Baseline avant travaux : 913 tests. Après : 913 + les nouveaux (≈ +8), 0 échec.

- [ ] **Step 3 : Lint**

Run :
```bash
uv run ruff check app/scrapers/raceresult.py tests/test_raceresult.py
```
Expected : « All checks passed! ».

- [ ] **Step 4 : Vérifier l'absence de warning parasite sur les fixtures existantes**

Run :
```bash
uv run pytest tests/test_raceresult.py -k scrape_event_all -q -W error::UserWarning
```
Expected : PASS — aucun test existant de `scrape_event_all` ne déclenche la nouvelle alerte (elle est muette sur les fusions légitimes du panel).

---

## Self-Review

**1. Couverture de la spec :**
- §3.1 (instrumentation) → Tasks 1 (helper) + 2 (warning). ✓
- §3.2 (épinglage cas mixte) → Task 3. ✓
- §3.3 (tests instrumentation) → Task 1 (unitaire) + Task 2 (intégration positive/négative). ✓
- §4 (note de clôture sondage) → Task 4. ✓
- §5 (critères d'acceptation : suite verte, muet sur le panel, comportement inchangé) → Task 5. ✓

**2. Placeholders :** aucun « TBD/TODO » ; chaque step porte le code ou la commande réelle. ✓

**3. Cohérence des types :** `_identites_incompatibles(a, b) -> bool` défini en Task 1, consommé sous ce nom exact en Task 2. `_identite_pliee` interne au helper. `_monte_pipeline`/`_payload` sont des helpers **existants** de `test_raceresult.py` (vérifiés lignes ~1607-1649), réutilisés tels quels. Le logger cible `app.scrapers.raceresult` est le `__name__` du module (ligne 53). ✓

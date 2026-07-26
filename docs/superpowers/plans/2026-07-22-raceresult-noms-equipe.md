# RaceResult — ne plus mutiler les noms d'équipe (issue #63) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empêcher `_build_result` (scraper RaceResult) de découper un nom d'équipe en (nom, prénom), tout en continuant de découper les noms de personne.

**Architecture:** La décision *découper ou non* passe dans `_build_result`, gardée par un prédicat `_est_nom_equipe(nom_col_expr, valeur)` : garde par valeur (`&`) + garde par colonne (expression source d'équipe non conditionnelle). L'expression source de la colonne « nom » est re-dérivée par `_nom_expression(payload, roles)` et threadée via un kwarg défaulté. `split_athlete_name` (partagé) n'est **pas** touché. L'angle mort résiduel (nom d'équipe sans `&` sur colonne conditionnelle) est loggé, pas traité.

**Tech Stack:** Python 3.13, uv, pytest, ruff. Tests unitaires sans réseau. Commandes depuis `backend/`.

## Global Constraints

- **Ne jamais modifier `split_athlete_name`** (`backend/app/scrapers/utils.py`) : partagé par tous les scrapers ; des noms de personne légitimes portent `/` ou `-`.
- **Ne pas modifier la signature de `_map_columns`** : dépliée par ~25 call sites de tests.
- UI, commentaires, messages en **français** avec accents.
- Commits Conventional Commits ; finir le message par `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Tests unitaires **sans réseau**. Lancer avec `uv run pytest -m "not integration"`.
- Lint : `uv run ruff check .` doit passer.
- Constante partagée par les gardes : `_CHAMPS_NOM_EQUIPE = ("nomrelais", "nomequipe", "affichernoms")`.

Spec de référence : `docs/superpowers/specs/2026-07-22-raceresult-noms-equipe-design.md`.

---

## File Structure

- `backend/app/scrapers/raceresult.py` — ajoute le cluster « nom d'équipe » (constante + 3 helpers) juste avant `_build_result`, branche la garde dans `_build_result` (+ kwarg), et le calcul + log dans `scrape_event_all`.
- `backend/tests/test_raceresult.py` — tests unitaires des helpers + bout-en-bout `_build_result` + test de log via `scrape_event_all`.
- `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` — §12.3 / §12.4 marqués « corrigé (#63) ».

---

### Task 1 : Helpers de détection (`_est_nom_equipe`, `_nom_expression`, `_colonne_nom_conditionnelle_equipe`)

**Files:**
- Modify: `backend/app/scrapers/raceresult.py` (insérer le cluster juste avant `def _build_result(` — actuellement ~ligne 841)
- Test: `backend/tests/test_raceresult.py`

**Interfaces:**
- Consumes : `_peel(expr) -> str` et `_RE_COMPARAISON` (déjà dans `raceresult.py`).
- Produces :
  - `_CHAMPS_NOM_EQUIPE: tuple[str, ...]`
  - `_est_nom_equipe(nom_col_expr: str, valeur: str) -> bool`
  - `_nom_expression(payload: dict, roles: dict[str, int]) -> str`
  - `_colonne_nom_conditionnelle_equipe(nom_col_expr: str) -> bool`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_raceresult.py` :

```python
# ── Noms d'équipe : ne pas découper (issue #63) ─────────────────────────────
@pytest.mark.parametrize("expr,valeur,attendu", [
    # Garde par colonne : expression d'équipe inconditionnelle.
    ("NomRelais", "Les Inconnus Associés", True),
    ("ucase([NomRelais])", "les bleus", True),
    ("AfficherNoms", "Dupont Jean, Martin Paul", True),
    # Garde par valeur : `&` sépare deux personnes, quelle que soit la colonne.
    ("AfficherNom", "GUILLAUME & ANTHONY", True),
    ("if([Relais]=1;ucase([NomRelais]);[AfficherNom])", "GUILLAUME & ANTHONY", True),
    # Individus : à découper (aucune garde ne fire).
    ("AfficherNom", "Florian VIDAL", False),
    ("LFNAME", "DUPONT Jean", False),
    # Colonne conditionnelle sans `&` : individu, à découper (garde 2 exclut le
    # conditionnel — sinon `_peel` la réduirait à `nomrelais` et casserait les
    # individus de cette colonne mixte).
    ("if([Relais]=1;ucase([NomRelais]);[AfficherNom])", "Florian VIDAL", False),
])
def test_est_nom_equipe(expr, valeur, attendu):
    assert raceresult._est_nom_equipe(expr, valeur) is attendu


def test_nom_expression_rend_l_expression_de_la_colonne_nom():
    payload = _payload_401699_relais()
    roles, _segments, _extras = raceresult._map_columns(payload)
    assert raceresult._nom_expression(payload, roles) == "NomRelais"


def test_nom_expression_vide_sans_colonne_nom():
    assert raceresult._nom_expression({"DataFields": ["BIB"]}, {"bib": 0}) == ""


@pytest.mark.parametrize("expr,attendu", [
    # Conditionnelle capable de rendre une équipe → à signaler.
    ("if([Relais]=1;ucase([NomRelais]);[AfficherNom])", True),
    # Conditionnelle non d'équipe (pèle vers affichernom) → pas de signal.
    ("if([STATUS]<>2;[AfficherNom])", False),
    # Colonne d'équipe inconditionnelle → gérée par la garde 2, pas d'angle mort.
    ("NomRelais", False),
    ("AfficherNoms", False),
])
def test_colonne_nom_conditionnelle_equipe(expr, attendu):
    assert raceresult._colonne_nom_conditionnelle_equipe(expr) is attendu
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_raceresult.py -k "est_nom_equipe or nom_expression or colonne_nom_conditionnelle" -q`
Expected: FAIL avec `AttributeError: module 'app.scrapers.raceresult' has no attribute '_est_nom_equipe'` (idem pour les autres).

- [ ] **Step 3 : Implémenter le cluster de helpers**

Dans `backend/app/scrapers/raceresult.py`, insérer **juste avant** `def _build_result(` :

```python
# ── Noms d'équipe : ne pas les découper en (nom, prénom) (issue #63) ─────────
#
# `split_athlete_name` (partagé, `scrapers/utils.py`) est calibré pour un nom de
# personne. Sur un nom d'équipe (« GUILLAUME & ANTHONY », « Les Inconnus
# Associés »), il mutile l'identité. On ne le corrige pas là — d'autres scrapers
# en dépendent, et des noms de personne portent `/` ou `-` — mais on garde son
# appel dans `_build_result`, à partir de deux signaux propres à RaceResult.
_CHAMPS_NOM_EQUIPE = ("nomrelais", "nomequipe", "affichernoms")


def _est_nom_equipe(nom_col_expr: str, valeur: str) -> bool:
    """Vrai si la cellule « nom » porte un nom d'équipe, à ne pas découper.

    Deux gardes :

    1. **Par valeur** : `&` sépare deux personnes (« GUILLAUME & ANTHONY »). Il
       n'apparaît jamais dans un nom de personne, contrairement à `/` ou `-`
       (que `split_athlete_name` doit continuer de couper) : garde sûre, valable
       même sur une colonne mixte. La virgule est écartée — `LFNAME` rend
       « NOM, Prénom » pour un individu.
    2. **Par colonne** : `NomRelais` / `NomEquipe` / `AfficherNoms` (pluriel :
       les équipiers) sert une colonne **entièrement** d'équipe. La
       conditionnelle `if([Relais]=1;[NomRelais];[AfficherNom])` en est exclue :
       elle mêle équipes et individus ligne à ligne, et `_peel` la réduit à
       `nomrelais` — traiter alors toute la colonne en équipe cesserait de
       découper ses individus. Ses lignes d'équipe retombent sur la garde 1.
    """
    if "&" in valeur:
        return True
    if ";" in nom_col_expr or _RE_COMPARAISON.search(nom_col_expr):
        return False
    return _peel(nom_col_expr) in _CHAMPS_NOM_EQUIPE


def _colonne_nom_conditionnelle_equipe(nom_col_expr: str) -> bool:
    """Colonne « nom » conditionnelle capable de rendre une équipe (angle mort #63).

    Une conditionnelle `if([Relais]=1;ucase([NomRelais]);[AfficherNom])` mêle
    équipes et individus : un nom d'équipe **sans `&`** y échappe aux deux gardes
    de `_est_nom_equipe`. On ne peut pas le détecter ligne à ligne (le champ
    `[Relais]` par ligne n'est pas exposé de façon fiable), mais on repère la
    colonne — conditionnelle **et** pelant vers un champ d'équipe — pour la
    signaler. `if([STATUS]<>2;[AfficherNom])` pèle vers `affichernom` → False.
    """
    if ";" not in nom_col_expr and not _RE_COMPARAISON.search(nom_col_expr):
        return False
    return _peel(nom_col_expr) in _CHAMPS_NOM_EQUIPE


def _nom_expression(payload: dict, roles: dict[str, int]) -> str:
    """Expression source de la colonne ayant gagné le rôle « nom » (issue #63).

    `_map_columns` ne retient que l'index de colonne ; on re-dérive l'expression
    depuis `DataFields` pour que les gardes ci-dessus puissent juger la colonne.
    `""` si l'épreuve n'expose pas de colonne « nom ».
    """
    col = roles.get("nom")
    if col is None:
        return ""
    data_fields = [str(e) for e in payload.get("DataFields") or []]
    return data_fields[col] if col < len(data_fields) else ""
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run: `cd backend && uv run pytest tests/test_raceresult.py -k "est_nom_equipe or nom_expression or colonne_nom_conditionnelle" -q`
Expected: PASS (18 cas paramétrés + 2 unitaires).

- [ ] **Step 5 : Lint**

Run: `cd backend && uv run ruff check app/scrapers/raceresult.py tests/test_raceresult.py`
Expected: `All checks passed!`

- [ ] **Step 6 : Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "feat(raceresult): helpers de détection de nom d'équipe (#63)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2 : Brancher la garde dans `_build_result` + `scrape_event_all` (calcul, thread, log)

**Files:**
- Modify: `backend/app/scrapers/raceresult.py` (`_build_result` signature + branche de garde ~ligne 879 ; `scrape_event_all` ~lignes 1195 et 1222-1229)
- Test: `backend/tests/test_raceresult.py`

**Interfaces:**
- Consumes : `_est_nom_equipe`, `_nom_expression`, `_colonne_nom_conditionnelle_equipe`, `_CHAMPS_NOM_EQUIPE` (Task 1), `split_athlete_name`, `_strip_rank_suffix`, `logger`, `event_id`.
- Produces : `_build_result(..., nom_col_expr: str = "")` — nouveau kwarg défaulté, keyword-only.

- [ ] **Step 1 : Écrire les tests bout-en-bout qui échouent**

Ajouter à `backend/tests/test_raceresult.py` (après les tests de Task 1) :

```python
def _payload_nom_affichernoms():
    """Liste où la colonne « nom » est AfficherNoms (duo SwimRun, forme 403144)."""
    return {
        "DataFields": ["BIB", "ID", "AfficherNoms", "OuStatut([TIME])"],
        "list": {"Fields": [
            {"Expression": "BIB", "Label": "Dos."},
            {"Expression": "AfficherNoms", "Label": "Équipe"},
            {"Expression": "OuStatut([TIME])", "Label": "Temps"},
        ]},
        "data": {"#1_SwimRun L": [["12", "34", "GUILLAUME & ANTHONY", "1:20:00"]]},
    }


def _payload_nom_affichernom_individuel():
    """Liste individuelle standard : la colonne « nom » est AfficherNom."""
    return {
        "DataFields": ["BIB", "ID", "AfficherNom", "OuStatut([TIME])"],
        "list": {"Fields": [
            {"Expression": "BIB", "Label": "Dos."},
            {"Expression": "AfficherNom", "Label": "Nom"},
            {"Expression": "OuStatut([TIME])", "Label": "Temps"},
        ]},
        "data": {"#1_Individuel": [["7", "8", "Florian VIDAL", "1:00:00"]]},
    }


def _construire_avec_expr(payload, ligne, contest):
    """Construit un résultat en threadant l'expression de la colonne « nom »."""
    roles, segments, extras = raceresult._map_columns(payload)
    return raceresult._build_result(
        ligne, roles, segments, extras,
        source_url="https://my.raceresult.com/1/results",
        event_name="Épreuve",
        event_date=date(2026, 6, 21),
        contest_label=contest,
        status_label="",
        nom_col_expr=raceresult._nom_expression(payload, roles),
    )


def test_build_result_ne_decoupe_pas_un_nom_relais():
    """Un nom d'équipe non majuscule (colonne NomRelais) reste entier."""
    payload = _payload_401699_relais()
    ligne = list(payload["data"]["#1_Relais"][0])
    ligne[3] = "Les Inconnus Associés"  # colonne NomRelais (index 3 de DataFields)

    r = _construire_avec_expr(payload, ligne, "Relais")

    assert r.athlete_name == "Les Inconnus Associés"
    assert r.athlete_firstname == ""


def test_build_result_ne_decoupe_pas_un_nom_affichernoms():
    """« GUILLAUME & ANTHONY » (colonne AfficherNoms) reste entier."""
    payload = _payload_nom_affichernoms()
    ligne = payload["data"]["#1_SwimRun L"][0]

    r = _construire_avec_expr(payload, ligne, "SwimRun L")

    assert r.athlete_name == "GUILLAUME & ANTHONY"
    assert r.athlete_firstname == ""


def test_build_result_decoupe_toujours_un_individu():
    """Non-régression : un individu (colonne AfficherNom) est toujours découpé."""
    payload = _payload_nom_affichernom_individuel()
    ligne = payload["data"]["#1_Individuel"][0]

    r = _construire_avec_expr(payload, ligne, "Individuel")

    assert r.athlete_name == "VIDAL"
    assert r.athlete_firstname == "Florian"


def test_scrape_event_all_signale_la_colonne_nom_conditionnelle(monkeypatch):
    """Angle mort #63 : une colonne nom conditionnelle (mixte équipe/individu)
    est signalée — un nom d'équipe sans « & » y échappe aux deux gardes."""
    nom_expr = "if([Relais]=1;ucase([NomRelais]);[AfficherNom])"
    payload = {
        "DataFields": ["BIB", "ID", nom_expr, "TIME"],
        "list": {"Fields": [
            {"Expression": nom_expr, "Label": "Nom"},
            {"Expression": "TIME", "Label": "Temps"},
        ]},
        "data": {"#1_Distance S": {"#1_": [["7", "1", "Les Bleus", "01:00:00"]]}},
    }
    specs = [("Classement", "1")]
    _monte_pipeline(monkeypatch, specs, {("Classement", "1"): payload})

    with _capture_logs("app.scrapers.raceresult") as logs:
        raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    signaux = [rec for rec in logs.records if "angle mort #63" in rec.getMessage()]
    assert len(signaux) == 1
    assert nom_expr in signaux[0].getMessage()
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run: `cd backend && uv run pytest tests/test_raceresult.py -k "ne_decoupe_pas or decoupe_toujours or signale_la_colonne" -q`
Expected: FAIL. Les `_build_result(...)` échouent sur `nom_col_expr` (`TypeError: _build_result() got an unexpected keyword argument 'nom_col_expr'`) ; le test de log ne trouve pas le signal.

- [ ] **Step 3 : Ajouter le kwarg et la branche de garde dans `_build_result`**

Dans `backend/app/scrapers/raceresult.py`, ajouter le paramètre keyword-only à la signature de `_build_result` (après `status_label: str,`) :

```python
    status_label: str,
    nom_col_expr: str = "",
) -> ScrapedResult:
```

Puis remplacer la ligne :

```python
    nom, prenom = split_athlete_name(_strip_rank_suffix(cellule("nom")))
```

par :

```python
    # Nom d'équipe (issue #63) : `split_athlete_name` le mutilerait
    # (« GUILLAUME & ANTHONY » → nom='GUILLAUME', prenom='& ANTHONY »). On garde
    # alors la cellule entière comme `nom`, `prenom` vide. Cf. `_est_nom_equipe`.
    nom_cell = _strip_rank_suffix(cellule("nom"))
    if _est_nom_equipe(nom_col_expr, nom_cell):
        nom, prenom = nom_cell, ""
    else:
        nom, prenom = split_athlete_name(nom_cell)
```

- [ ] **Step 4 : Câbler `scrape_event_all` (calcul, log, thread)**

Dans `backend/app/scrapers/raceresult.py`, dans `scrape_event_all`, remplacer :

```python
            roles, segments, extras = _map_columns(payload)
```

par :

```python
            roles, segments, extras = _map_columns(payload)
            nom_col_expr = _nom_expression(payload, roles)
            if _colonne_nom_conditionnelle_equipe(nom_col_expr):
                logger.warning(
                    "RaceResult %s : colonne nom conditionnelle (%r) mêlant "
                    "équipes et individus — un nom d'équipe sans '&' peut être "
                    "découpé sans trace (angle mort #63)",
                    event_id, nom_col_expr,
                )
```

Puis, dans l'appel `_build_result(...)` juste en dessous, ajouter le kwarg (après `status_label=status_label,`) :

```python
                        contest_label=libelle,
                        status_label=status_label,
                        nom_col_expr=nom_col_expr,
                    )
```

- [ ] **Step 5 : Lancer les tests ciblés, vérifier le succès**

Run: `cd backend && uv run pytest tests/test_raceresult.py -k "ne_decoupe_pas or decoupe_toujours or signale_la_colonne" -q`
Expected: PASS (4 tests).

- [ ] **Step 6 : Lancer toute la suite RaceResult (non-régression, dont 401699)**

Run: `cd backend && uv run pytest tests/test_raceresult.py tests/test_scrapers_utils.py -q`
Expected: PASS — en particulier `test_build_result_categorie_i18n_de_401699_entre_lisible` (`"COLLER AU PARQUET"`) reste vert.

- [ ] **Step 7 : Lint**

Run: `cd backend && uv run ruff check app/scrapers/raceresult.py tests/test_raceresult.py`
Expected: `All checks passed!`

- [ ] **Step 8 : Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "fix(raceresult): ne plus découper un nom d'équipe en (nom, prénom) (#63)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3 : Documentation — sondage §12.3 / §12.4 « corrigé (#63) »

**Files:**
- Modify: `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` (§12.3 et §12.4)

**Interfaces:** aucune (documentation).

- [ ] **Step 1 : Marquer §12.3 comme corrigé**

Dans `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`, à la fin du **§12.3 Découpage des noms d'équipe**, après le paragraphe « Non trivial, d'où le ticket… », ajouter :

```markdown

**Corrigé (#63).** `_build_result` ne découpe plus une cellule « nom » reconnue
comme nom d'équipe : garde par valeur (`&`) + garde par colonne (expression
source `NomRelais`/`NomEquipe`/`AfficherNoms` non conditionnelle). Le nom entier
va dans `nom`, `prenom` vide. `split_athlete_name` (partagé) reste intact.
Détail : `2026-07-22-raceresult-noms-equipe-design.md`. Angle mort assumé et
**loggé** : un nom d'équipe sans `&` servi par une colonne conditionnelle
(`if([Relais]=1;ucase([NomRelais]);[AfficherNom])`) échappe aux deux gardes ;
`scrape_event_all` le signale (`logger.warning`, « angle mort #63 »).
```

- [ ] **Step 2 : Renvoyer depuis §12.4**

Dans le même fichier, à la fin du **§12.4 `is_relay` n'est pas la cause…**, après le paragraphe « Même avec une détection de relais parfaite… La mutilation (§12.3) est un défaut distinct, et il reste ouvert. », remplacer « et il reste ouvert. » par « et il est désormais corrigé (#63, cf. §12.3). ».

Édition exacte — remplacer :

```markdown
Même avec une détection de relais parfaite, le nom d'équipe serait découpé à
l'identique. La mutilation (§12.3) est un défaut distinct, et il reste ouvert.
```

par :

```markdown
Même avec une détection de relais parfaite, le nom d'équipe serait découpé à
l'identique. La mutilation (§12.3) est un défaut distinct, désormais corrigé
(#63, cf. §12.3).
```

- [ ] **Step 3 : Vérifier la cohérence**

Run: `cd backend && grep -n "corrigé (#63)\|angle mort #63" ../docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`
Expected: les deux ajouts apparaissent (§12.3 corrigé + renvoi §12.4).

- [ ] **Step 4 : Commit**

```bash
git add docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md
git commit -m "docs(raceresult): §12.3/§12.4 du sondage — mutilation des noms d'équipe corrigée (#63)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage :**
- §3.1 garde par valeur `&` + garde par colonne non conditionnelle → Task 1 (`_est_nom_equipe`) + tests.
- §3.1 exclusion du conditionnel (piège `_peel → nomrelais`) → Task 1, cas `("if(...)", "Florian VIDAL", False)`.
- §3.2 threading via `_nom_expression` + kwarg défaulté → Task 1 (`_nom_expression`) + Task 2 (signature + appel).
- §3.3 forme cible (nom entier, prénom vide) → Task 2, `test_build_result_ne_decoupe_pas_*`.
- §4 angle mort loggé (colonne conditionnelle) → Task 1 (`_colonne_nom_conditionnelle_equipe`) + Task 2 (log + `test_scrape_event_all_signale_la_colonne_nom_conditionnelle`).
- §5 non-régression 401699 + individu → Task 2 Step 6 + `test_build_result_decoupe_toujours_un_individu`.
- §6 doc → Task 3.

**Placeholder scan :** aucun TBD/TODO ; tout le code et toutes les commandes sont explicites.

**Type consistency :** `_est_nom_equipe(str, str) -> bool`, `_nom_expression(dict, dict) -> str`, `_colonne_nom_conditionnelle_equipe(str) -> bool`, `_build_result(..., nom_col_expr: str = "")` — noms et signatures identiques entre Task 1, Task 2 et les tests. `_CHAMPS_NOM_EQUIPE` défini une fois (Task 1), consommé par les deux prédicats.

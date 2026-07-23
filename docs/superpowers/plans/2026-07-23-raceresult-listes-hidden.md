# RaceResult — élargir aux listes `hidden` par jointure sur dossard — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Récupérer les données réelles portées par les listes `hidden` de RaceResult (splits du 406211) en les rattachant, **par dossard**, aux participants déjà établis par les listes publiées — sans jamais créer de participant ni de contest.

**Architecture:** `scrape_event_all` gagne une **3ᵉ phase d'enrichissement** après la fusion des listes publiées. Les listes publiées font autorité pour `dossard → contest` (index `cles_par_dossard`) ; chaque ligne d'une liste `hidden`, appariée par dossard, **complète** le `ScrapedResult` publié correspondant (splits si absents, scalaires vides) via `_enrichir`. Le libellé de groupe des lignes `hidden` n'est jamais consulté. Un dossard ambigu (réutilisé entre contests, verrou #21) ou absent du publié est ignoré (log).

**Tech Stack:** Python 3.13, pytest, httpx, `uv`. Module `backend/app/scrapers/raceresult.py`, tests `backend/tests/test_raceresult.py`, fixtures `backend/tests/fixtures/raceresult/`.

## Global Constraints

- Toujours lancer les commandes depuis `backend/`, via `uv run` (aucun venv à activer).
- Le cache uv doit pointer vers un répertoire inscriptible : `export UV_CACHE_DIR="${TMPDIR:-/tmp/claude-1001}/uv-cache"` en tête de chaque session shell.
- Tests unitaires **sans réseau** (défaut CI : `-m "not integration"`). Le réseau réel est isolé derrière `@pytest.mark.integration`.
- Langue : commentaires, messages et libellés en **français** (avec accents).
- TDD strict : test d'abord, le voir échouer, puis implémentation minimale.
- Commits : Conventional Commits, référencer `(#60)`.
- Ne **jamais** créer de participant ni de contest depuis une liste `hidden` : enrichissement seul.
- Ne **jamais** revenir au critère `Live`, ni à la route `/{id}/RRPublish/data/…`.
- Le `Name` de liste n'est **jamais** un qualifiant ni un critère de tri (§3 du sondage).
- Verrou C (rang sans point `'2:05:29 (2)'`, 410891) **hors périmètre**.

**Spec de référence :** `docs/superpowers/specs/2026-07-23-raceresult-listes-hidden-design.md`.

---

### Task 1 : Séparer les specs de listes publiées et `hidden`

**Files:**
- Modify: `backend/app/scrapers/raceresult.py:172-222` (`_iter_list_specs`)
- Test: `backend/tests/test_raceresult.py` (près de `test_iter_list_specs_*`, ~ligne 219)

**Interfaces:**
- Produces:
  - `_lists_or_raise(config: dict) -> list[dict]` — entrées de `TabConfig.Lists` bien formées (dict avec `Name`), lève `ValueError` sur forme inattendue.
  - `_iter_list_specs(config: dict) -> list[tuple[str, str]]` — inchangé fonctionnellement : couples `(listname, contest)` des listes **non-`hidden`**.
  - `_iter_hidden_list_specs(config: dict) -> list[tuple[str, str]]` — couples `(listname, contest)` des listes **`hidden`**.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter dans `backend/tests/test_raceresult.py` :

```python
def test_iter_hidden_list_specs_ne_rend_que_les_hidden():
    """#60 : symétrique de `_iter_list_specs`. Les listes `hidden` sont la
    matière de l'enrichissement ; on les prend toutes (le tri par la valeur se
    fait à l'exécution), indépendamment du Name et du Contest."""
    config = {"TabConfig": {"Lists": [
        {"Name": "Classement", "Contest": "1", "Mode": ""},
        {"Name": "Classement général", "Contest": "0", "Mode": "hidden"},
        {"Name": "Liste des Inscrits", "Contest": "0", "Mode": "hidden"},
        {"Name": "Sans nom", "Contest": "2", "Mode": "hidden"},  # écartée : pas de Name
    ]}}
    del config["TabConfig"]["Lists"][3]["Name"]
    assert raceresult._iter_hidden_list_specs(config) == [
        ("Classement général", "0"),
        ("Liste des Inscrits", "0"),
    ]


def test_iter_hidden_list_specs_leve_sur_une_forme_inattendue():
    """Même garde que `_iter_list_specs` : une `TabConfig.Lists` absente trahit
    la route héritée."""
    with pytest.raises(ValueError, match="TabConfig.Lists"):
        raceresult._iter_hidden_list_specs({"lists": []})
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run: `uv run pytest tests/test_raceresult.py -k "iter_hidden_list_specs" -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_iter_hidden_list_specs'`

- [ ] **Step 3 : Implémenter**

Dans `raceresult.py`, remplacer le corps de `_iter_list_specs` (lignes 210-222, la partie qui lit `TabConfig.Lists` et filtre) par un helper partagé, et ajouter la fonction `hidden`. Conserver **tel quel** le long docstring existant de `_iter_list_specs`. Concrètement :

```python
def _lists_or_raise(config: dict) -> list[dict]:
    """Entrées bien formées de `TabConfig.Lists`, ou `ValueError`.

    Une `TabConfig.Lists` absente ou de mauvaise forme trahit l'interrogation
    de la route héritée `/{id}/RRPublish/data/…` (cf. en-tête du module). Garde
    partagée par la sélection publiée et la sélection `hidden` (#60).
    """
    lists = (config.get("TabConfig") or {}).get("Lists")
    if not isinstance(lists, list):
        raise ValueError(
            f"TabConfig.Lists de forme inattendue : {type(lists)!r} "
            "(route héritée interrogée par erreur ?)"
        )
    return [item for item in lists if isinstance(item, dict) and item.get("Name")]


def _iter_list_specs(config: dict) -> list[tuple[str, str]]:
    """<DOCSTRING EXISTANT CONSERVÉ INTÉGRALEMENT>"""
    return [
        (str(item.get("Name")), str(item.get("Contest") or "0"))
        for item in _lists_or_raise(config)
        if item.get("Mode") != "hidden"
    ]


def _iter_hidden_list_specs(config: dict) -> list[tuple[str, str]]:
    """Listes `hidden` : [(listname, contest), …], matière de l'enrichissement (#60).

    Symétrique de `_iter_list_specs`. Ces listes n'introduisent ni participant
    ni contest (cf. design #60) : elles ne font qu'enrichir, par dossard, un
    participant déjà établi par une liste publiée. On les prend **toutes**,
    indépendamment du `Name` (banni comme qualifiant, §3) et du `Contest` — le
    tri du grain (splits) et de l'ivraie (inscrits, colonnes vides, classement
    redondant) se fait à l'exécution, par la valeur des cellules. Une liste sans
    apport reste inerte.
    """
    return [
        (str(item.get("Name")), str(item.get("Contest") or "0"))
        for item in _lists_or_raise(config)
        if item.get("Mode") == "hidden"
    ]
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès (y compris non-régression)**

Run: `uv run pytest tests/test_raceresult.py -k "iter_list_specs or iter_hidden_list_specs" -v`
Expected: PASS (les tests existants `test_iter_list_specs_*` restent verts — comportement inchangé).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "feat(raceresult): sélection des listes hidden pour enrichissement (#60)"
```

---

### Task 2 : `_enrichir` — compléter un résultat publié sans jamais l'écraser

**Files:**
- Modify: `backend/app/scrapers/raceresult.py` (après `_prefer`, ~ligne 1174)
- Test: `backend/tests/test_raceresult.py` (nouvelle section)

**Interfaces:**
- Consumes: `ScrapedResult` (de `scrapers/base`).
- Produces:
  - `_CHAMPS_SCALAIRES_ENRICHISSABLES: tuple[str, ...]` = `("total_time", "club", "category", "gender")`.
  - `_enrichir(existant: ScrapedResult, apport: ScrapedResult) -> None` — mute `existant` en place ; comble les trous, n'écrase rien.

- [ ] **Step 1 : Écrire les tests qui échouent**

```python
def _res(**kw):
    """ScrapedResult minimal pour les tests d'enrichissement."""
    base = dict(source_url="u", provider="raceresult", bib_number="7")
    base.update(kw)
    return ScrapedResult(**base)


def test_enrichir_ajoute_les_splits_si_absents():
    existant = _res(athlete_name="DUPONT", total_time="01:00:00", segments=None)
    apport = _res(segments=[("Swim", "10:00"), ("Run", "20:00")])
    raceresult._enrichir(existant, apport)
    assert existant.segments == [("Swim", "10:00"), ("Run", "20:00")]
    assert existant.athlete_name == "DUPONT", "l'identité du publié est intouchée"


def test_enrichir_ne_fusionne_pas_deux_listes_de_splits():
    existant = _res(segments=[("Swim", "10:00")])
    apport = _res(segments=[("Bike", "30:00")])
    raceresult._enrichir(existant, apport)
    assert existant.segments == [("Swim", "10:00")], "les splits existants priment"


def test_enrichir_remplit_les_scalaires_vides():
    existant = _res(total_time="", club="", category="", gender="")
    apport = _res(total_time="01:23:45", club="TCN", category="V1", gender="M")
    raceresult._enrichir(existant, apport)
    assert (existant.total_time, existant.club, existant.category, existant.gender) == (
        "01:23:45", "TCN", "V1", "M",
    )


def test_enrichir_n_ecrase_jamais_un_scalaire_renseigne():
    existant = _res(total_time="01:00:00", club="ASPTT")
    apport = _res(total_time="09:99:99", club="AUTRE")
    raceresult._enrichir(existant, apport)
    assert existant.total_time == "01:00:00"
    assert existant.club == "ASPTT"


def test_enrichir_ne_touche_ni_identite_ni_rang_ni_statut():
    existant = _res(
        athlete_name="DUPONT", athlete_firstname="Jean",
        rank_overall=3, status="finisher",
    )
    apport = _res(
        athlete_name="AUTRE", athlete_firstname="Paul",
        rank_overall=99, status="DNF", segments=[("Swim", "10:00")],
    )
    raceresult._enrichir(existant, apport)
    assert existant.athlete_name == "DUPONT"
    assert existant.athlete_firstname == "Jean"
    assert existant.rank_overall == 3
    assert existant.status == "finisher"
    assert existant.segments == [("Swim", "10:00")]
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run: `uv run pytest tests/test_raceresult.py -k "enrichir" -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_enrichir'`

- [ ] **Step 3 : Implémenter**

Après `_prefer` (juste avant `_identite_pliee`, ~ligne 1176) :

```python
# Champs scalaires qu'une ligne `hidden` peut combler côté publié (#60). Le
# publié fait autorité : l'enrichissement ne remplit qu'un trou, jamais n'écrase.
# Volontairement restreint — nom/prénom, rangs, statut et dossard n'y figurent
# pas : ils sont l'identité et le classement établis par le publié.
_CHAMPS_SCALAIRES_ENRICHISSABLES = ("total_time", "club", "category", "gender")


def _enrichir(existant: ScrapedResult, apport: ScrapedResult) -> None:
    """Complète `existant` (ligne publiée) avec une ligne `hidden` appariée par
    dossard (#60). Mute `existant` en place ; comble les trous, n'écrase rien.

    - **Splits** : pris seulement si `existant` n'en avait **aucun**. On ne
      fusionne pas deux listes partielles de segments (cas non observé au panel ;
      inférence évitée) — cf. §7 du design.
    - **Scalaires** (`_CHAMPS_SCALAIRES_ENRICHISSABLES`) : remplis s'ils sont
      vides côté publié.
    - **Rien d'autre** : identité, rangs, statut, dossard et event_* restent ceux
      du publié. Un enrichissement ne peut pas dégrader ce qui est déjà établi.
    """
    if not existant.segments and apport.segments:
        existant.segments = apport.segments
    for champ in _CHAMPS_SCALAIRES_ENRICHISSABLES:
        if not getattr(existant, champ) and getattr(apport, champ):
            setattr(existant, champ, getattr(apport, champ))
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run: `uv run pytest tests/test_raceresult.py -k "enrichir" -v`
Expected: PASS (5 tests).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "feat(raceresult): _enrichir comble les trous d'un résultat publié (#60)"
```

---

### Task 3 : Phase d'enrichissement dans `scrape_event_all`

**Files:**
- Modify: `backend/app/scrapers/raceresult.py:1217-1332` (`scrape_event_all`, dans le bloc `with httpx.Client`)
- Modify: `backend/tests/test_raceresult.py:1741-1767` (`_monte_pipeline`, ajout du paramètre `hidden`)
- Test: `backend/tests/test_raceresult.py` (nouvelle section)

**Interfaces:**
- Consumes: `_iter_hidden_list_specs` (Task 1), `_enrichir` (Task 2), `_fetch_list`, `_map_columns`, `_nom_expression`, `_iter_groups`, `_build_result` (existants).
- Produces: comportement de `scrape_event_all` étendu ; signature inchangée. `_monte_pipeline(monkeypatch, specs, payloads, *, hidden=())` accepte des specs `hidden`.

- [ ] **Step 1 : Étendre le harnais de test `_monte_pipeline`**

Remplacer `_monte_pipeline` (lignes 1741-1767) par une version qui accepte des listes `hidden`. Le corps est identique, seule la construction de `Lists` et la signature changent :

```python
def _monte_pipeline(monkeypatch, specs, payloads, *, hidden=()):
    """Câble `scrape_event_all` sur des payloads en mémoire.

    `payloads` mappe (listname, contest) → payload ou None. `specs` sont les
    listes publiées, `hidden` les listes `Mode == "hidden"` (#60). Les appels
    sont enregistrés pour vérifier qu'aucun balayage à l'aveugle ne subsiste.
    """
    appels: list[tuple[str, str]] = []
    config = {
        "key": "k",
        "eventname": "Épreuve",
        "contests": {"1": "Distance S", "2": "Distance M"},
        "TabConfig": {"Lists":
            [{"Name": n, "Contest": c, "Mode": ""} for n, c in specs]
            + [{"Name": n, "Contest": c, "Mode": "hidden"} for n, c in hidden]
        },
    }
    monkeypatch.setattr(raceresult, "_resolve_event_id", lambda url, client: "1")
    monkeypatch.setattr(raceresult, "_fetch_config", lambda ev, client: config)
    monkeypatch.setattr(
        raceresult, "_fetch_meta", lambda ev, client: ("Épreuve", date(2026, 5, 24), "")
    )

    def faux_fetch(event_id, key, listname, contest, client):
        appels.append((listname, contest))
        return payloads.get((listname, contest))

    monkeypatch.setattr(raceresult, "_fetch_list", faux_fetch)
    return appels
```

- [ ] **Step 2 : Écrire les tests qui échouent**

Ajouter un builder de payload à colonnes de split, puis les tests. Placer près des autres tests `scrape_event_all` :

```python
def _payload_splits(lignes_par_groupe: dict) -> dict:
    """Payload d'un classement `hidden` portant nom + temps + 2 splits.

    Reproduit la forme réelle du 406211 : les segments sont enveloppés d'une
    conditionnelle `if([STATUS]=2;"";[X])` que `_peel` réduit à `[X]`.
    """
    champs = [
        {"Expression": "AfficherNom", "Label": "Nom"},
        {"Expression": 'if([STATUS]=2;"";[Natation])', "Label": "Swim"},
        {"Expression": 'if([STATUS]=2;"";[Course])', "Label": "Run"},
        {"Expression": "TIME", "Label": "Total"},
    ]
    data_fields = ["BIB", "ID", "AfficherNom",
                   'if([STATUS]=2;"";[Natation])', 'if([STATUS]=2;"";[Course])', "TIME"]
    return {"DataFields": data_fields, "list": {"Fields": champs},
            "data": lignes_par_groupe}


def test_scrape_event_all_hidden_enrichit_les_splits_par_dossard(monkeypatch):
    """#60 cas nominal (forme du 406211) : le publié porte identité + temps mais
    aucun split ; le classement `hidden` en Contest=0, groupé sous un libellé
    étranger, apporte les splits — rattachés par **dossard**, pas par libellé."""
    specs = [("LIVE", "1")]
    hidden = [("Classement", "0")]
    payloads = {
        ("LIVE", "1"): _payload({"#1_Distance S": {"#1_": [
            ["525", "1", "Martin SCHULZ", "TCN", "1:03:01"],
        ]}}),
        # Libellé de groupe volontairement DIFFÉRENT du contest publié :
        # « PTS5 Men » vs « Distance S ». La jointure ignore le libellé.
        ("Classement", "0"): _payload_splits({"#6_PTS5 Men": [
            ["525", "1", "Martin SCHULZ", "10:27", "18:57", "1:03:01"],
        ]}),
    }
    _monte_pipeline(monkeypatch, specs, payloads, hidden=hidden)

    res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert len(res) == 1, "aucun participant ajouté par le hidden"
    r = res[0]
    assert r.event_name == "Épreuve - Distance S", "le contest reste celui du publié"
    # `normalize_time` pade en hh:mm:ss : "10:27" -> "00:10:27".
    assert r.segments == [("Swim", "00:10:27"), ("Run", "00:18:57")]


def test_scrape_event_all_hidden_ne_cree_jamais_de_participant(monkeypatch):
    """Un dossard présent seulement dans une liste `hidden` (inscrit, DNS…) n'est
    pas rattachable : il est ignoré, jamais promu en participant fantôme."""
    specs = [("LIVE", "1")]
    hidden = [("Classement", "0")]
    payloads = {
        ("LIVE", "1"): _payload({"#1_Distance S": {"#1_": [
            ["525", "1", "Martin SCHULZ", "TCN", "1:03:01"],
        ]}}),
        ("Classement", "0"): _payload_splits({"#1_G": [
            ["525", "1", "Martin SCHULZ", "10:27", "18:57", "1:03:01"],
            ["999", "2", "Fantome INSCRIT", "05:00", "06:00", "12:00"],
        ]}),
    }
    _monte_pipeline(monkeypatch, specs, payloads, hidden=hidden)

    res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert {r.bib_number for r in res} == {"525"}


def test_scrape_event_all_hidden_dossard_ambigu_est_ignore_et_loggue(monkeypatch):
    """Verrou #21 : un dossard réutilisé entre deux contests publiés rend la
    jointure ambiguë. On n'enrichit pas (on ne devine pas) et on loggue."""
    specs = [("LIVE", "1"), ("LIVE", "2")]
    hidden = [("Classement", "0")]
    payloads = {
        ("LIVE", "1"): _payload({"#1_Distance S": {"#1_": [
            ["7", "1", "Jean DUPONT", "TCN", "01:00:00"],
        ]}}),
        ("LIVE", "2"): _payload({"#1_Distance M": {"#1_": [
            ["7", "2", "Luc MARTIN", "TCN", "02:00:00"],
        ]}}),
        ("Classement", "0"): _payload_splits({"#1_G": [
            ["7", "1", "Jean DUPONT", "10:00", "20:00", "01:00:00"],
        ]}),
    }
    _monte_pipeline(monkeypatch, specs, payloads, hidden=hidden)

    with _capture_logs("app.scrapers.raceresult") as logs:
        res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert all(r.segments is None for r in res), "dossard ambigu : aucun split enrichi"
    assert any("ambigu" in rec.getMessage() for rec in logs.records)


def test_scrape_event_all_hidden_sans_split_est_inerte(monkeypatch):
    """Une liste `hidden` redondante (mêmes colonnes que le publié, sans split :
    forme du classement Contest=0 du 410891) n'ajoute rien et ne casse rien."""
    specs = [("LIVE", "1")]
    hidden = [("Redondant", "0")]
    payloads = {
        ("LIVE", "1"): _payload({"#1_Distance S": {"#1_": [
            ["7", "1", "Jean DUPONT", "TCN", "01:00:00"],
        ]}}),
        ("Redondant", "0"): _payload({"#1_G": {"#1_": [
            ["7", "1", "Jean DUPONT", "TCN", "01:00:00"],
        ]}}),  # _payload : pas de colonne de split
    }
    _monte_pipeline(monkeypatch, specs, payloads, hidden=hidden)

    res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert len(res) == 1
    assert res[0].segments is None
    assert res[0].club == "TCN"
```

- [ ] **Step 3 : Lancer les tests, vérifier l'échec**

Run: `uv run pytest tests/test_raceresult.py -k "hidden_enrichit or hidden_ne_cree or hidden_dossard_ambigu or hidden_sans_split" -v`
Expected: FAIL — le `hidden` n'est pas encore fetché ni enrichi (splits absents, ou `TypeError` si `_monte_pipeline` non encore étendu au Step 1).

- [ ] **Step 4 : Implémenter la phase d'enrichissement**

Dans `scrape_event_all`, **à l'intérieur** du bloc `with httpx.Client(...)`, juste après la fin de la boucle « Phase 2 » (après la ligne `fusion[cle] = r`, actuellement ligne 1332) et **avant** la sortie du `with` :

```python
        # Phase 3 : enrichissement par les listes `hidden` (#60).
        # Les listes publiées font autorité pour `dossard → contest` : on indexe
        # les clés de fusion par dossard, puis on rattache chaque ligne `hidden`
        # par ce dossard. Le libellé de groupe des lignes `hidden` n'est jamais
        # consulté (§4.2 du design) — `_iter_groups` n'est réutilisé que pour
        # aplatir l'arbre `data` de profondeur variable en lignes.
        cles_par_dossard: dict[str, list[tuple[str, str]]] = {}
        for cle in fusion:
            cles_par_dossard.setdefault(cle[1], []).append(cle)

        for listname, contest in _iter_hidden_list_specs(config):
            payload = _fetch_list(event_id, key, listname, contest, client)
            if payload is None:
                continue
            roles, segments, extras = _map_columns(payload)
            nom_col_expr = _nom_expression(payload, roles)
            for _contest_label, _status_label, lignes in _iter_groups(
                payload.get("data"), contests_connus=contests_connus
            ):
                for ligne in lignes:
                    apport = _build_result(
                        ligne, roles, segments, extras,
                        source_url=url,
                        event_name=event_name,
                        event_date=jour,
                        contest_label="",
                        status_label="",
                        nom_col_expr=nom_col_expr,
                    )
                    if not apport.bib_number:
                        continue
                    cles = cles_par_dossard.get(apport.bib_number)
                    if not cles:
                        logger.debug(
                            "RaceResult %s : dossard hidden %s absent des listes "
                            "publiées, ignoré (jamais de participant fantôme, #60)",
                            event_id, apport.bib_number,
                        )
                        continue
                    if len(cles) > 1:
                        logger.warning(
                            "RaceResult %s : dossard %s ambigu (contests %s) — "
                            "enrichissement hidden ignoré, jointure non résoluble "
                            "(verrou #21, #60)",
                            event_id, apport.bib_number, [c[0] for c in cles],
                        )
                        continue
                    _enrichir(fusion[cles[0]], apport)
```

- [ ] **Step 5 : Lancer les tests, vérifier le succès**

Run: `uv run pytest tests/test_raceresult.py -k "hidden_enrichit or hidden_ne_cree or hidden_dossard_ambigu or hidden_sans_split" -v`
Expected: PASS (4 tests).

- [ ] **Step 6 : Non-régression complète du module**

Run: `uv run pytest tests/test_raceresult.py -q -m "not integration"`
Expected: PASS — les 245 tests existants + les nouveaux.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "feat(raceresult): enrichir les participants publiés depuis les listes hidden (#60)"
```

---

### Task 4 : Test sur payloads réels capturés (fixtures 406211 + non-régression 410891/411749)

**Files:**
- Create (versionner) : `backend/tests/fixtures/raceresult/406211_config.json`, `406211_hidden_classement.json`, `406211_pub_contest{1..13}.json`, `410891_config.json`, `410891_hidden_c0.json`, `410891_inter_c1.json`, `410891_inscrits_c1.json`, `410891_pub_c1.json`, `411749_config.json` (déjà présents sur disque dans le worktree).
- Test: `backend/tests/test_raceresult.py` (nouvelle section « fixtures réelles #60 »)

**Interfaces:**
- Consumes: `raceresult.scrape_event_all`, helpers `_fixture` (existant, lit `tests/fixtures/`), `FIXTURES`.

- [ ] **Step 1 : Vérifier que les fixtures sont présentes**

Run: `ls backend/tests/fixtures/raceresult/ | sort`
Expected: les fichiers ci-dessus (21 fichiers `.json`).

- [ ] **Step 2 : Écrire le test qui échoue**

```python
import json as _json

RR_FIXTURES = FIXTURES / "raceresult"


def _monte_pipeline_fixtures(monkeypatch, event_id, routeur):
    """Câble `scrape_event_all` sur les payloads réels capturés.

    `routeur(listname, contest)` rend le nom de fichier fixture, ou None si la
    liste n'a pas été capturée (le code de prod traite alors None comme un 404).
    """
    config = _json.loads((RR_FIXTURES / f"{event_id}_config.json").read_text("utf-8"))
    monkeypatch.setattr(raceresult, "_resolve_event_id", lambda url, client: event_id)
    monkeypatch.setattr(raceresult, "_fetch_config", lambda ev, client: config)
    monkeypatch.setattr(
        raceresult, "_fetch_meta",
        lambda ev, client: (config.get("eventname", ""), date(2026, 6, 1), ""),
    )

    def faux_fetch(ev, key, listname, contest, client):
        nom = routeur(listname, contest)
        if nom is None:
            return None
        payload = _json.loads((RR_FIXTURES / nom).read_text("utf-8"))
        return payload if payload.get("data") else None

    monkeypatch.setattr(raceresult, "_fetch_list", faux_fetch)


def test_scrape_event_all_406211_recupere_les_splits_du_classement_hidden(monkeypatch):
    """#60, données réelles (World Triathlon Para Cup, 2026-07-23) : les 13
    listes publiées portent identité + temps mais 0 split ; le classement
    `hidden` Contest=0 apporte Swim/T1/Bike/T2/Run. La jointure par dossard
    résout la granularité (PTS2 Men + PTS3 Men → PTS2-3 M, PTVI Men → PTVI2-3 M)
    que l'appariement de libellés ne pouvait pas."""
    def routeur(listname, contest):
        if listname == "01-Résultats en ligne|LIVE":
            return f"406211_pub_contest{contest}.json"
        if listname == "01-Classements|Classement général" and contest == "0":
            return "406211_hidden_classement.json"
        return None  # « Concurrents » non capturé → traité comme 404

    _monte_pipeline_fixtures(monkeypatch, "406211", routeur)

    res = raceresult.scrape_event_all("https://my.raceresult.com/406211/results")

    assert len(res) == 42, "42 dossards publiés, aucun ajouté par le hidden"
    avec_splits = [r for r in res if r.segments]
    assert len(avec_splits) == 33, "les 33 lignes du classement hidden enrichies"
    labels = {lab for r in avec_splits for lab, _ in r.segments}
    assert labels == {"Swim", "T1", "Bike", "T2", "Run"}
    # Contrôle ponctuel : Martin SCHULZ (dossard 525, contest PTS5 M) porte ses 5
    # splits, et son contest reste celui du publié — pas « PTS5 Men » du hidden.
    schulz = next(r for r in res if r.bib_number == "525")
    assert schulz.event_name.endswith("PTS5 M")
    # `normalize_time` pade en hh:mm:ss.
    assert dict(schulz.segments) == {
        "Swim": "00:10:27", "T1": "00:00:50", "Bike": "00:32:13",
        "T2": "00:00:34", "Run": "00:18:57",
    }


def test_scrape_event_all_410891_hidden_reste_inerte(monkeypatch):
    """#60 non-régression : sur 410891, le classement hidden Contest=0 est
    redondant (pas de split) et les splits `inter` sont au format `'…(2)'` (rang
    sans point, verrou C hors périmètre) — rejetés par `_RE_DUREE`. La phase
    d'enrichissement n'ajoute donc aucun split, et n'introduit aucun participant
    (les inscrits sont ignorés)."""
    def routeur(listname, contest):
        table = {
            ("Classements|Classement général", "1"): "410891_pub_c1.json",
            ("Classements|Classement général", "0"): "410891_hidden_c0.json",
            ("Classements|Classement général inter 2", "1"): "410891_inter_c1.json",
            ("Concurrents|Liste des Inscrits", "1"): "410891_inscrits_c1.json",
        }
        return table.get((listname, contest))

    _monte_pipeline_fixtures(monkeypatch, "410891", routeur)

    res = raceresult.scrape_event_all("https://my.raceresult.com/410891/results")

    assert res, "les listes publiées produisent des participants"
    assert all(r.segments is None for r in res), "aucun split (verrou C, colonnes inertes)"
```

- [ ] **Step 3 : Lancer le test, vérifier l'échec initial puis le succès**

Run: `uv run pytest tests/test_raceresult.py -k "406211_recupere or 410891_hidden_reste_inerte" -v`
Expected: PASS après implémentation des Tasks 1-3. Si un test échoue sur un compte (`42`/`33`), lire le message : c'est un révélateur de bug d'implémentation, pas un test à ajuster.

- [ ] **Step 4 : Commit**

```bash
git add backend/tests/fixtures/raceresult/ backend/tests/test_raceresult.py
git commit -m "test(raceresult): fixtures réelles 406211/410891/411749 + enrichissement hidden (#60)"
```

---

### Task 5 : Test d'intégration réseau réel (isolé du CI)

**Files:**
- Test: `backend/tests/test_integration_scrapers.py` (ajout d'un test marqué `integration`)

**Interfaces:**
- Consumes: `raceresult.scrape_event_all` (réseau réel vers `my.raceresult.com`).

- [ ] **Step 1 : Repérer le style des tests d'intégration existants**

Run: `grep -n "pytest.mark.integration\|def test_" backend/tests/test_integration_scrapers.py | head`
Expected: confirme le marqueur et le style (assertions souples : bornes min, pas d'égalités figées sur des données vivantes).

- [ ] **Step 2 : Écrire le test d'intégration**

Ajouter dans `backend/tests/test_integration_scrapers.py` (adapter les imports au fichier) :

```python
@pytest.mark.integration
def test_raceresult_406211_enrichit_les_splits_en_reel():
    """#60 réseau réel : le classement hidden du 406211 doit apporter les splits
    aux finishers. Assertions souples (données vivantes) : au moins une dizaine
    de participants portent 5 segments Swim/T1/Bike/T2/Run."""
    from app.scrapers import raceresult

    res = raceresult.scrape_event_all("https://my.raceresult.com/406211/results")

    avec_splits = [r for r in res if r.segments]
    assert len(avec_splits) >= 10
    ref = next(r for r in avec_splits if len(r.segments) == 5)
    assert {lab for lab, _ in ref.segments} == {"Swim", "T1", "Bike", "T2", "Run"}
```

- [ ] **Step 3 : Lancer le test d'intégration (réseau requis, respecter le délai)**

Run: `uv run pytest tests/test_integration_scrapers.py -k "406211_enrichit" -v -m integration`
Expected: PASS (nécessite un accès réseau à `my.raceresult.com`). En l'absence de réseau, le test n'est pas joué par le CI par défaut (`-m "not integration"`).

- [ ] **Step 4 : Vérifier qu'il n'est pas joué par la cible unitaire**

Run: `uv run pytest tests/test_integration_scrapers.py -k "406211_enrichit" -m "not integration" -q`
Expected: `no tests ran` (le marqueur l'exclut bien).

- [ ] **Step 5 : Commit**

```bash
git add backend/tests/test_integration_scrapers.py
git commit -m "test(raceresult): intégration réseau réel du 406211 (#60)"
```

---

### Task 6 : Documentation — amender le sondage et AGENTS.md

**Files:**
- Modify: `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` (§4.2)
- Modify: `AGENTS.md` (paragraphe RaceResult sur les listes `hidden`)

**Interfaces:** aucune (documentation).

- [ ] **Step 1 : Amender le §4.2 du sondage**

Ajouter à la fin du §4.2 un encart d'amendement daté, sans supprimer l'existant (le sondage consigne l'historique) :

```markdown
**(amendement 2026-07-23, issue #60 résolue pour (A)+(B))** : la mesure d'origine
présentait l'écart comme `'PTS5 Men'` ↔ `'PTS5 M'` (graphie). Re-mesuré sur 406211,
l'écart est de **partition** : `PTS2 Men` + `PTS3 Men` (hidden) → `PTS2-3 M`
(publié), `PTVI Men` → éclaté en `PTVI1 M`/`PTVI2-3 M`. Aucun appariement de
libellés ne réconcilie une fusion ni un éclatement. La réconciliation retenue est
donc une **jointure par dossard** : les listes publiées font autorité pour
`dossard → contest`, les lignes `hidden` s'y rattachent par dossard, en
**enrichissement seul** (jamais de participant ni de contest créé). Mesuré : 42
dossards publiés uniques, 33 dossards hidden tous résolus vers un seul contest ;
406211 gagne 5 splits × 33. Le **verrou C** (410891, `'2:05:29 (2)'`, rang sans
point) reste ouvert : l'élargissement l'expose mais `_RE_DUREE` le rejette encore.
Design : `2026-07-23-raceresult-listes-hidden-design.md`.
```

- [ ] **Step 2 : Amender AGENTS.md**

Dans le paragraphe RaceResult, remplacer la phrase « L'élargissement aux listes `hidden` est **différé** derrière la réconciliation des libellés de contest, ni réfuté ni clos (cf. §4.2 du sondage). » par :

```markdown
L'élargissement aux listes `hidden` est **réalisé** (#60) : elles ne créent ni
participant ni contest, elles **enrichissent** par **dossard** les participants
établis par les listes publiées (splits, scalaires vides). Coût : une requête
`list` par liste `hidden`. Le verrou C (410891, rang `(2)` sans point) reste
ouvert. Design : `2026-07-23-raceresult-listes-hidden-design.md`.
```

- [ ] **Step 3 : Vérifier la cohérence (pas de contradiction résiduelle)**

Run: `grep -n "hidden" AGENTS.md`
Expected: plus aucune mention de « différé » pour l'élargissement `hidden`.

- [ ] **Step 4 : Commit**

```bash
git add AGENTS.md docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md
git commit -m "docs(raceresult): élargissement hidden réalisé par jointure sur dossard (#60)"
```

---

## Notes d'exécution

- **Ordre des tâches** : 1 → 2 → 3 sont séquentielles (3 dépend de 1 et 2). 4 dépend de 3. 5 et 6 dépendent de 3 mais sont indépendantes l'une de l'autre.
- **Après chaque tâche** : `uv run ruff check .` doit rester vert (analyse statique du projet).
- **Cache uv** : si une commande `uv` échoue sur `Read-only file system … /.cache/uv`, exporter `UV_CACHE_DIR="${TMPDIR:-/tmp/claude-1001}/uv-cache"`.
- **Réseau** : seules les commandes de la Task 5 touchent le réseau. Sonder en série, ~3 s de délai (§13.4 du sondage) si des sondes manuelles sont ajoutées.

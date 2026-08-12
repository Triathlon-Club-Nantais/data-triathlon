# ProLiveSport — résolution des rôles de split (issue #280)

> **Pour les agents :** SOUS-COMPÉTENCE REQUISE — utiliser
> `superpowers:executing-plans` ou `superpowers:subagent-driven-development`
> pour exécuter ce plan tâche par tâche, **sur désignation explicite de
> l'utilisateur** (AGENTS.md : l'exécuteur Superpowers n'a pas de défaut). Les
> étapes sont en cases à cocher (`- [ ]`) pour le suivi.

**Objectif :** corriger `backend/app/scrapers/prolivesport.py` pour qu'aucun
temps stocké en `bike_time`/`run_time` (ni `swim_time`/`t1_time`/`t2_time`) ne
soit un point de passage intermédiaire au lieu d'une durée de section, sans
perdre aucun point de passage publié par la source.

**Spec de référence :** `docs/superpowers/specs/2026-08-12-prolivesport-splits-design.md`
(design approuvé, mesures du sondage `docs/superpowers/specs/2026-08-12-prolivesport-splits-sondage.md`
— 4 événements réels / 28 courses le 2026-08-12). En cas de doute, le sondage
prime sur le design, qui prime sur ce plan.

**État de vérification** : ce plan **n'a pas été exécuté**. Conformément à
`docs/WORKFLOW-IA.md`, la voie Superpowers s'arrête après le design et ce
plan tant que l'utilisateur n'a pas nommé l'exécuteur (`executing-plans` ou
`subagent-driven-development`) — contrairement au plan `oktime` cité en
référence de style, dont le code avait été assemblé et exécuté avant
publication. Les comptes de tests annoncés ci-dessous (« 53 aujourd'hui » etc.)
sont mesurés sur l'état actuel de `tests/test_prolivesport.py` ; les comptes
« après la tâche » sont des **cibles**, à vérifier par l'exécuteur.

## Contraintes globales

- **Langue** : code, commentaires, docstrings, messages de log et noms de test
  en **français avec accents** (convention déjà en place dans ce module).
- **Tests sans réseau** : `uv run pytest tests/test_prolivesport.py -v` passe
  hors ligne. Aucun test `integration` n'est requis par ce correctif (le
  sondage a déjà interrogé la source réelle, les fixtures suffisent pour la
  non-régression).
- **Commandes** : depuis `backend/`. Pas de venv à activer, `uv run` s'en
  charge.
- **Lint** : `uv run ruff check .` propre à chaque commit (E402, F401 actifs —
  compléter le bloc d'imports existant en tête de fichier, ne jamais insérer
  un import au milieu).
- **TDD strict** : test rouge → implémentation minimale → test vert → commit.
- **Commits** : Conventional Commits, suffixés `(#280)`.
- **Ne pas toucher** `services/mapping.py` : le comportement « `segments`
  prime entièrement sur les 5 slots positionnels » est un invariant partagé
  par tous les scrapers (cf. design, section « Pourquoi tout ou rien »). Le
  correctif reste intégralement dans `prolivesport.py` et ses tests.
- **Pas de régression sur le fan-out (#269)** : `scrape_event_fanout` et
  `scrape_event_all` restent responsables du regroupement par `race` et de la
  reprise sur 500 — ce plan ne touche que la construction des splits et
  l'appel qu'ils en font.

---

## Structure des fichiers

| Fichier | Responsabilité |
| --- | --- |
| `backend/app/scrapers/prolivesport.py` (modifié) | `_build_split_map` renvoie une résolution par rôle **et** la liste complète des champs ; `_parse_athlete` bascule en `segments` dès qu'un rôle est ambigu ; les deux appelants (`scrape_event_fanout`, `scrape_event_all`) transmettent la nouvelle forme. |
| `backend/tests/test_prolivesport.py` (modifié) | Tests de `_build_split_map` migrés vers la nouvelle forme de retour ; nouveaux tests d'ambiguïté et de non-régression sur la carte 979 de l'issue ; tests `_parse_athlete` existants (candidat unique) inchangés dans leur intention, adaptés à la nouvelle signature. |
| `docs/scrapers/prolivesport.md` (modifié) | Section « Défaut connu, hors périmètre (#280) » remplacée par le comportement retenu. |

---

## Rappel : ce qui existe déjà et ne se réécrit pas

```python
# app/scrapers/base.py
@dataclass
class ScrapedResult:
    ...
    swim_time: str = ""; t1_time: str = ""; bike_time: str = ""
    t2_time: str = ""; run_time: str = ""
    segments: list[tuple[str, str]] | None = None   # prime sur les 5 slots si renseigné

# app/scrapers/prolivesport.py — labels par rôle, INCHANGÉS par ce plan
_SWIM_LABELS = {"swim", "nat", "cat/nat", "natation"}
_T1_LABELS   = {"#1", "t1", "trans1", "transition1"}
_BIKE_LABELS  = {"bike", "velo", "vélo", "cycle", "bikestart"}
_T2_LABELS   = {"#2", "t2", "trans2", "transition2"}
_RUN_LABELS  = {"run", "cap", "course", "courseapied", "c.a.p"}
```

Le classement libellé → rôle (`_SWIM_LABELS` etc.) n'est **pas** en cause : le
sondage confirme qu'un champ qui matche un rôle porte bien cette discipline
(constat n° 2/3). Le défaut est dans la **résolution** quand plusieurs champs
matchent le même rôle, pas dans la détection elle-même.

---

### Tâche 1 : `_build_split_map` détecte l'ambiguïté et expose tous les champs

**Fichiers :**
- Modifier : `backend/app/scrapers/prolivesport.py`
- Modifier : `backend/tests/test_prolivesport.py`

**Interfaces :**
- Consomme : rien de nouveau (mêmes `_SWIM_LABELS` etc.).
- Produit :
  - `_SplitPlan` (NamedTuple) : `resolved: dict[str, str]` (rôle → champ, un
    seul candidat), `ambigu: bool` (au moins un rôle à ≥ 2 candidats),
    `tous_les_champs: list[tuple[str, str]]` (`(field, label)`, triés par
    suffixe numérique du champ, **tous** les champs de la course — matchés ou
    non).
  - `_build_split_map(splits: list, race: str) -> _SplitPlan` (signature
    changée — l'ancien retour `dict[str, str]` disparaît).

- [ ] **Étape 1 : écrire les tests qui échouent**

Remplacer `test_build_split_map_filters_by_race` (nom conservé, contenu
adapté à la nouvelle forme) et ajouter les cas d'ambiguïté :

```python
def test_build_split_map_un_seul_candidat_par_role():
    splits = [
        {"race": "S", "field": "Nat", "label": "Natation"},
        {"race": "S", "field": "Tr1", "label": "T1"},
        {"race": "S", "field": "Velo", "label": "Vélo"},
        {"race": "S", "field": "Tr2", "label": "T2"},
        {"race": "S", "field": "Cap", "label": "Course à pied"},
        {"race": "M", "field": "AutreNat", "label": "Natation"},  # autre course → ignoré
    ]
    plan = _build_split_map(splits, race="S")
    assert plan.resolved == {
        "swim": "Nat", "t1": "Tr1", "bike": "Velo", "t2": "Tr2", "run": "Cap",
    }
    assert plan.ambigu is False


def test_build_split_map_ambiguite_carte_979():
    """Carte exacte citée par l'issue #280 : bike a 3 candidats (T3/T6/T7),
    run en a 2 (T5/T8)."""
    splits = [
        {"race": "M", "field": "T1", "label": "Swim"},
        {"race": "M", "field": "T2", "label": "#1"},
        {"race": "M", "field": "T3", "label": "Bike"},
        {"race": "M", "field": "T4", "label": "#2"},
        {"race": "M", "field": "T5", "label": "Run"},
        {"race": "M", "field": "T6", "label": "BikeStart"},
        {"race": "M", "field": "T7", "label": "BikeEnd"},
        {"race": "M", "field": "T8", "label": "RunStart"},
    ]
    plan = _build_split_map(splits, race="M")
    assert plan.resolved == {"swim": "T1", "t1": "T2", "t2": "T4"}  # bike/run absents : ambigus
    assert plan.ambigu is True
    assert plan.tous_les_champs == [
        ("T1", "Swim"), ("T2", "#1"), ("T3", "Bike"), ("T4", "#2"),
        ("T5", "Run"), ("T6", "BikeStart"), ("T7", "BikeEnd"), ("T8", "RunStart"),
    ]


def test_build_split_map_libelle_non_reconnu_reste_dans_tous_les_champs():
    """`Split1` (event 1082/1079) ne matche aucun rôle : absent de `resolved`,
    présent dans `tous_les_champs` — nécessaire pour ne rien perdre si la
    course bascule en `segments` pour une autre raison."""
    splits = [
        {"race": "M", "field": "T1", "label": "Bike"},
        {"race": "M", "field": "T9", "label": "Split1"},
    ]
    plan = _build_split_map(splits, race="M")
    assert plan.resolved == {"bike": "T1"}
    assert plan.ambigu is False
    assert plan.tous_les_champs == [("T1", "Bike"), ("T9", "Split1")]


def test_build_split_map_tri_par_suffixe_numerique_du_champ():
    """L'ordre de la réponse API est mélangé (mesuré) : `tous_les_champs` est
    trié sur le suffixe numérique, pas sur l'ordre d'arrivée."""
    splits = [
        {"race": "M", "field": "T9", "label": "Split1"},
        {"race": "M", "field": "T3", "label": "Bike"},
        {"race": "M", "field": "T1", "label": "Swim"},
    ]
    plan = _build_split_map(splits, race="M")
    assert [f for f, _ in plan.tous_les_champs] == ["T1", "T3", "T9"]
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_prolivesport.py -v -k build_split_map
```
Attendu : ÉCHEC — `AttributeError`/`ImportError` (`_SplitPlan` inexistant,
ancien retour `dict` incompatible avec `.resolved`).

- [ ] **Étape 3 : écrire l'implémentation minimale**

```python
from typing import NamedTuple


class _SplitPlan(NamedTuple):
    """Résolution des rôles de split pour une course (#280).

    `resolved` ne porte que les rôles à candidat **unique** : un rôle à
    ≥ 2 candidats (mesuré sur l'événement 979 : bike ← Bike/BikeStart/BikeEnd)
    ne peut pas être tranché sans deviner lequel des champs est la vraie durée
    de section — il est donc exclu, et `ambigu` le signale à l'appelant.
    `tous_les_champs` porte l'intégralité des champs de la course, triés par
    suffixe numérique (`T3` → 3) : nécessaire pour reconstruire `segments`
    sans rien perdre quand `ambigu` est vrai (cf. design, "tout ou rien").
    """
    resolved: dict[str, str]
    ambigu: bool
    tous_les_champs: list[tuple[str, str]]


def _numero_champ(field: str) -> int:
    """Suffixe numérique d'un champ (`"T3"` → `3`), 0 si illisible."""
    m = re.search(r"\d+", field)
    return int(m.group()) if m else 0


def _build_split_map(splits: list, race: str) -> _SplitPlan:
    """Construit la résolution des rôles de split pour une course (#280).

    Un rôle avec un seul champ candidat est résolu ; à partir de deux, aucun
    des deux n'est retenu (cf. sondage/design : rien ne permet de trancher
    lequel est la durée de section plutôt qu'un point cumulé redondant).
    """
    candidats: dict[str, list[str]] = {}
    champs_de_la_course: list[tuple[str, str]] = []
    for s in splits:
        if s.get("race", "").lower() != race.lower():
            continue
        field = s.get("field", "")
        label_brut = s.get("label") or s.get("displayTitle") or ""
        champs_de_la_course.append((field, label_brut))
        label = re.sub(r"\s+", "", label_brut).lower()
        if any(lbl in label for lbl in _SWIM_LABELS):
            candidats.setdefault("swim", []).append(field)
        elif any(lbl == label for lbl in _T1_LABELS):
            candidats.setdefault("t1", []).append(field)
        elif any(lbl in label for lbl in _BIKE_LABELS):
            candidats.setdefault("bike", []).append(field)
        elif any(lbl == label for lbl in _T2_LABELS):
            candidats.setdefault("t2", []).append(field)
        elif any(lbl in label for lbl in _RUN_LABELS):
            candidats.setdefault("run", []).append(field)

    resolved = {role: fields[0] for role, fields in candidats.items() if len(fields) == 1}
    ambigu = any(len(fields) > 1 for fields in candidats.values())
    champs_de_la_course.sort(key=lambda fc: _numero_champ(fc[0]))
    return _SplitPlan(resolved=resolved, ambigu=ambigu, tous_les_champs=champs_de_la_course)
```

Ajouter `from typing import NamedTuple` au bloc d'imports existant (avec les
imports `collections.abc`, `datetime`, `urllib.parse` déjà présents).

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_prolivesport.py -v && uv run ruff check .
```
Attendu : les 4 tests ci-dessus PASS. `test_build_split_map_filters_by_race`
disparaît (remplacé) — vérifier qu'aucun autre test du fichier n'appelle
encore `_build_split_map` en attendant un `dict` brut (tâche 3 les migre).

- [ ] **Étape 5 : commit**

```bash
git add backend/app/scrapers/prolivesport.py backend/tests/test_prolivesport.py
git commit -m "fix(scrapers): prolivesport détecte l'ambiguïté de rôle de split (#280)"
```

---

### Tâche 2 : `_parse_athlete` bascule en `segments` quand un rôle est ambigu

**Fichiers :**
- Modifier : `backend/app/scrapers/prolivesport.py`
- Modifier : `backend/tests/test_prolivesport.py`

**Interfaces :**
- Consomme : `_SplitPlan` (tâche 1).
- Produit : `_parse_athlete(athlete, plan: _SplitPlan, url, event_name,
  event_type, event_date) -> ScrapedResult` — **signature changée** (le
  paramètre `split_map: dict` devient `plan: _SplitPlan`).

- [ ] **Étape 1 : écrire les tests qui échouent**

Adapter les tests `_parse_athlete` existants à la nouvelle signature (candidat
unique par rôle → comportement inchangé, seul le type du deuxième argument
change) :

```python
def test_parse_athlete_fields_and_splits():
    athlete = {
        "lastname": "Dupont", "firstname": "Jean", "number": "42", "club": "TCN",
        "categoryRef": "S3H", "sex": "H", "rank": "5", "rankSex": "4", "rankCat": "1",
        "time": "01:59:00", "timeNat": "00:11:00", "timeTr1": "00:01:00",
        "timeVelo": "01:05:00", "timeTr2": "00:00:50", "timeCap": "00:41:10",
    }
    plan = _SplitPlan(
        resolved={"swim": "Nat", "t1": "Tr1", "bike": "Velo", "t2": "Tr2", "run": "Cap"},
        ambigu=False,
        tous_les_champs=[],  # non utilisé hors ambiguïté
    )
    r = _parse_athlete(athlete, plan, "http://x", "Triathlon Test", "triathlon-s", None)

    assert r.swim_time == "00:11:00"
    assert r.bike_time == "01:05:00"
    assert r.run_time == "00:41:10"
    assert r.segments is None  # pas d'ambiguïté → pas de segments


def test_parse_athlete_ambiguite_route_tout_vers_segments():
    """Non-régression de l'issue #280, carte exacte de l'événement 979."""
    athlete = {
        "lastname": "Dupont", "number": "245", "time": "01:45:17",
        "timeT1": "00:20:42", "timeT2": "00:01:29", "timeT3": "00:51:31",
        "timeT4": "00:01:12", "timeT5": "00:30:25", "timeT6": "00:22:11",
        "timeT7": "01:13:41", "timeT8": "01:14:53",
    }
    plan = _SplitPlan(
        resolved={"swim": "T1", "t1": "T2", "t2": "T4"},  # bike/run ambigus → absents
        ambigu=True,
        tous_les_champs=[
            ("T1", "Swim"), ("T2", "#1"), ("T3", "Bike"), ("T4", "#2"),
            ("T5", "Run"), ("T6", "BikeStart"), ("T7", "BikeEnd"), ("T8", "RunStart"),
        ],
    )
    r = _parse_athlete(athlete, plan, "http://x", "E", "triathlon-m", None)

    assert r.bike_time == ""
    assert r.run_time == ""
    assert r.swim_time == ""  # tout ou rien : même un rôle non ambigu part en segments
    assert r.t1_time == ""
    assert r.t2_time == ""
    assert r.segments == [
        ("Swim", "00:20:42"), ("#1", "00:01:29"), ("Bike", "00:51:31"),
        ("#2", "00:01:12"), ("Run", "00:30:25"), ("BikeStart", "00:22:11"),
        ("BikeEnd", "01:13:41"), ("RunStart", "01:14:53"),
    ]


def test_parse_athlete_ambiguite_ignore_les_champs_vides_dans_segments():
    athlete = {
        "lastname": "Test", "number": "1", "time": "01:00:00",
        "timeT3": "00:30:00", "timeT6": "",
    }
    plan = _SplitPlan(resolved={}, ambigu=True, tous_les_champs=[("T3", "Bike"), ("T6", "BikeStart")])

    r = _parse_athlete(athlete, plan, "http://x", "E", "triathlon-m", None)

    assert r.segments == [("Bike", "00:30:00")]  # BikeStart vide → écarté, comme les slots aujourd'hui
```

- [ ] **Étape 2 : lancer les tests et vérifier qu'ils échouent**

```bash
uv run pytest tests/test_prolivesport.py -v -k parse_athlete
```
Attendu : ÉCHEC — `TypeError` (signature `_parse_athlete` inchangée n'accepte
pas encore un `_SplitPlan`) ou `AttributeError` sur `plan.resolved`.

- [ ] **Étape 3 : écrire l'implémentation minimale**

```python
def _parse_athlete(athlete: dict, plan: _SplitPlan, url: str, event_name: str, event_type: str, event_date) -> ScrapedResult:
    result = ScrapedResult(source_url=url, provider="prolivesport")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date

    result.athlete_name = athlete.get("lastname", "").strip().upper()
    result.athlete_firstname = athlete.get("firstname", "").strip()
    result.bib_number = athlete.get("number", "")
    result.club = athlete.get("club", "")
    result.category = athlete.get("categoryRef", athlete.get("category", ""))
    result.gender = athlete.get("sex", "")
    result.is_relay = _is_relay(athlete)
    result.status = _derive_status(athlete)
    if result.status == STATUS_FINISHER:
        result.rank_overall = normalize_rank(athlete.get("rank"))
        result.rank_gender = normalize_rank(athlete.get("rankSex"))
        result.rank_category = normalize_rank(athlete.get("rankCat"))
        result.total_time = normalize_time(athlete.get("time", ""))

    if plan.ambigu:
        # Au moins un rôle a ≥ 2 candidats (#280) : impossible de trancher lequel
        # est la durée de section plutôt qu'un point cumulé redondant. Toute la
        # course part dans `segments` — y compris les rôles non ambigus, car
        # `mapping.build_splits` fait primer `segments` en entier sur les 5 slots
        # positionnels (aucune fusion) : les laisser dans les slots les ferait
        # disparaître silencieusement de `Participation.splits`.
        result.segments = [
            (label, t)
            for field, label in plan.tous_les_champs
            if (t := normalize_time(athlete.get(f"time{field}", ""))) and t != "00:00:00"
        ]
    else:
        for role, field in plan.resolved.items():
            t = normalize_time(athlete.get(f"time{field}", ""))
            if not t or t == "00:00:00":
                continue
            setattr(result, f"{role}_time", t)

    result.raw_data = {k: v for k, v in athlete.items() if not k.isdigit()}
    return result
```

Le `setattr(result, f"{role}_time", t)` remplace le `if/elif` en chaîne
existant : avec `plan.resolved` garanti à un seul candidat par rôle, plus
besoin de « garder le premier non vide » — chaque rôle n'a qu'une seule
source possible. Vérifier que les 5 noms de rôle (`swim`, `t1`, `bike`, `t2`,
`run`) correspondent exactement aux attributs `swim_time`/`t1_time`/
`bike_time`/`t2_time`/`run_time` de `ScrapedResult` (c'est le cas).

- [ ] **Étape 4 : lancer les tests et vérifier qu'ils passent**

```bash
uv run pytest tests/test_prolivesport.py -v && uv run ruff check .
```
Attendu : tous les tests de `_parse_athlete` PASS, y compris les tests
préexistants de statut (`test_parse_athlete_dns_clears_time_and_ranks` etc.)
qui passent `plan={}`-like non ambigu — **vérifier** qu'ils sont bien migrés
vers `_SplitPlan(resolved={}, ambigu=False, tous_les_champs=[])` à la place de
l'ancien `{}`.

- [ ] **Étape 5 : commit**

```bash
git add backend/app/scrapers/prolivesport.py backend/tests/test_prolivesport.py
git commit -m "fix(scrapers): prolivesport route les rôles ambigus vers segments (#280)"
```

---

### Tâche 3 : appelants, fan-out, et documentation

**Fichiers :**
- Modifier : `backend/app/scrapers/prolivesport.py` (`scrape_event_fanout`,
  `scrape_event_all`)
- Modifier : `backend/tests/test_prolivesport.py` (tests de fan-out qui
  appellent `_build_split_map`/`_parse_athlete` indirectement via les fixtures
  `SPLITS_979` — vérifier qu'aucun ne dépend de l'ancien retour `dict`)
- Modifier : `docs/scrapers/prolivesport.md`

**Interfaces :**
- Consomme : `_SplitPlan`, `_build_split_map`, `_parse_athlete` (tâches 1-2).
- Ne change pas : la signature publique `scrape_event_fanout(url, *,
  cache_probe=None, on_heat_start=None)` / `scrape_event_all(url)`.

- [ ] **Étape 1 : identifier les deux call sites**

Dans `scrape_event_fanout` :
```python
for race, sub_url in a_scraper:
    split_map = _build_split_map(splits, race)
    ...
    _parse_athlete(ligne, split_map, sub_url, nom, event_type, event_date)
```
Dans `scrape_event_all` :
```python
split_map = _build_split_map(_fetch_splits(event_id, client), race)
...
_parse_athlete(a, split_map, url, nom, event_type, event_date)
```

Ces deux lignes fonctionnent **sans modification** : `_build_split_map` rend
désormais un `_SplitPlan` au lieu d'un `dict`, et `_parse_athlete` attend
justement un `_SplitPlan` en second paramètre (tâche 2). Renommer la variable
locale `split_map` en `plan` dans les deux fonctions, par clarté — pas un
changement fonctionnel.

- [ ] **Étape 2 : lancer la suite complète et vérifier qu'elle échoue seulement là où attendu**

```bash
uv run pytest tests/test_prolivesport.py -v
```
Attendu à ce stade (avant renommage) : déjà vert, puisque le second paramètre
est positionnel et que son type a changé de façon transparente pour ces deux
appels. Le renommage `split_map` → `plan` est cosmétique ; s'assurer qu'aucun
test de fan-out (`test_fanout_split_map_par_course_en_un_seul_appel` etc.) ne
manipule directement un `dict` issu de `_build_split_map` — sinon l'adapter
au `_SplitPlan` comme en tâche 1.

- [ ] **Étape 3 : appliquer le renommage cosmétique**

```python
# scrape_event_fanout
for race, sub_url in a_scraper:
    plan = _build_split_map(splits, race)
    ...
    resultats.extend(
        _parse_athlete(ligne, plan, sub_url, nom, event_type, event_date)
        for ligne in lignes.get(race, [])
    )

# scrape_event_all
plan = _build_split_map(_fetch_splits(event_id, client), race)
...
return [
    _parse_athlete(a, plan, url, nom, event_type, event_date)
    for a in athletes
    if (a.get("race") or "").strip() == race
]
```

- [ ] **Étape 4 : test d'intégration du fan-out sur la carte 979**

Ajouter aux fixtures existantes (`SPLITS_979`, déjà présentes dans le fichier)
les champs `BikeStart`/`BikeEnd`/`RunStart` pour reproduire fidèlement
l'ambiguïté mesurée sur la vraie course « Triathlon M », et un test bout-en-
bout :

```python
def test_fanout_ambiguite_de_role_route_vers_segments(monkeypatch):
    """Non-régression #280 en conditions de fan-out : la course Triathlon M a
    ses rôles bike/run ambigus (Bike/BikeStart/BikeEnd, Run/RunStart) → aucun
    des deux slots n'est renseigné, tout part dans `segments`."""
    splits_avec_ambiguite = SPLITS_979 + [
        {"race": "Triathlon M", "field": "T6", "label": "BikeStart"},
        {"race": "Triathlon M", "field": "T7", "label": "BikeEnd"},
        {"race": "Triathlon M", "field": "T5", "label": "Run"},
        {"race": "Triathlon M", "field": "T8", "label": "RunStart"},
    ]
    _api(monkeypatch, splits=splits_avec_ambiguite)

    resultats, _trace = prolivesport.scrape_event_fanout(URL_979)

    m = [r for r in resultats if r.raw_data["race"] == "Triathlon M"]
    assert all(r.bike_time == "" and r.run_time == "" for r in m)
    assert all(r.segments for r in m)
```

Lancer, vérifier l'échec puis le succès, comme les étapes précédentes.

- [ ] **Étape 5 : mettre à jour `docs/scrapers/prolivesport.md`**

Remplacer la section « Défaut connu, hors périmètre (#280) » (lignes finales
du fichier) par :

```markdown
## Rôles de split ambigus : résolus par candidat unique (#280)

Un rôle (`swim`/`t1`/`bike`/`t2`/`run`) peut avoir plusieurs champs candidats
— mesuré sur l'événement 979 : `bike` reçoit `Bike`, `BikeStart` **et**
`BikeEnd` (les trois contiennent la sous-chaîne `"bike"`), `run` reçoit `Run`
**et** `RunStart`. Le sondage
(`docs/superpowers/specs/2026-08-12-prolivesport-splits-sondage.md`) établit
que le champ nommé exactement par la discipline (`Bike`, `Run`) est une durée
de section fiable (la somme des 5 champs canoniques colle au temps total à
2 s près), tandis que les variantes `*Start`/`*End` sont des points cumulés
depuis le départ — la même information sous une autre forme, pas une donnée
supplémentaire.

**Règle retenue** : un rôle à candidat **unique** alimente son slot
positionnel comme avant. Dès qu'un rôle a **deux candidats ou plus** pour une
course, aucun slot positionnel n'est renseigné pour **toute la course** (y
compris les rôles non ambigus) — tous ses champs partent dans
`ScrapedResult.segments`, triés par suffixe numérique de champ, avec le
libellé source conservé tel quel. Le « tout ou rien » vient de
`services/mapping.build_splits`, qui fait primer `segments` en entier sur les
5 slots dès qu'il est renseigné : laisser un rôle non ambigu dans son slot
alors que `segments` est actif le ferait disparaître de
`Participation.splits`. Détail : `docs/superpowers/specs/2026-08-12-prolivesport-splits-design.md`.

Les libellés génériques sans rapport avec les 5 rôles connus (`SplitN` sur
1082/1079, `SportN` sur les événements duathlon comme 1060) restent hors
`splits`/`segments` quand ils n'accompagnent aucune ambiguïté — deviner leur
discipline romprait le principe de simplicité. Ils restent lisibles dans
`raw_data` (`timeT9`, `timeSport2`…), ce qui suffit au critère « rien n'est
perdu ».
```

- [ ] **Étape 6 : lancer la suite complète et `ruff`**

```bash
uv run pytest tests/test_prolivesport.py -v && uv run ruff check .
uv run pytest -m "not integration"   # suite complète : aucune régression ailleurs
```
Attendu : tous les tests PASS (53 existants − 1 remplacé + les nouveaux des
tâches 1-3 ; compte exact à relever par l'exécuteur), `ruff` propre, aucune
régression sur le reste de la suite (aucun autre module n'importe
`_build_split_map`/`_parse_athlete`/`_SplitPlan` — vérifié par
`grep -rn "_build_split_map\|_parse_athlete" backend/app backend/tests` avant
de conclure).

- [ ] **Étape 7 : commit**

```bash
git add backend/app/scrapers/prolivesport.py backend/tests/test_prolivesport.py \
        docs/scrapers/prolivesport.md
git commit -m "fix(scrapers): prolivesport — appelants et doc pour la résolution de splits (#280)"
```

---

## Après ce plan

`requesting-code-review` → `verification-before-completion` →
`finishing-a-development-branch`, communs aux trois voies (AGENTS.md). Ni le
fan-out, ni les commits par tâche ne se déclenchent d'eux-mêmes : l'exécuteur
suit ce plan tâche par tâche et s'arrête à la fin de la tâche 3 en attendant
la revue.

# Élargir le verrou C aux splits de segment — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Récupérer les splits intermédiaires des finishers RaceResult (rang suffixé sans point) tout en conservant ceux des non-finishers, sans relâcher `_RE_DUREE` ni le décollage strict de `nom`/`club`/`temps`.

**Architecture:** Ajout d'une variante permissive `_strip_rank_suffix_segment` du décollage de rang, employée uniquement dans le pipeline de construction des segments (gardé en aval par `_RE_DUREE`). `_strip_rank_suffix` (strict, §12.2) reste inchangé pour le texte libre.

**Tech Stack:** Python 3.13, pytest, uv, ruff. Module `backend/app/scrapers/raceresult.py`, tests `backend/tests/test_raceresult.py`.

## Global Constraints

- Commandes depuis `backend/` ; `uv run …` (aucun venv à activer).
- **Cache uv en sandbox** : exporter `UV_CACHE_DIR="$TMPDIR/uv-cache"` avant tout `uv run` (le cache `~/.cache/uv` est en lecture seule).
- Tests unitaires **sans réseau** (les fixtures 410891 sont locales, montées par `_monte_pipeline_fixtures`).
- Langue FR avec accents pour code/commentaires/messages.
- Commits Conventional Commits ; ne **pas** pousser sans accord.
- Ne **rien** changer à `_RE_DUREE`, `normalize_time`, ni au chemin `nom`/`club`/`temps`.

---

### Task 1: Variante permissive `_strip_rank_suffix_segment`

**Files:**
- Modify: `backend/app/scrapers/raceresult.py:556-577` (helpers de décollage)
- Test: `backend/tests/test_raceresult.py` (après `test_strip_rank_suffix`, ~ligne 421)

**Interfaces:**
- Consumes: `_RE_RANG_SUFFIXE` (permissif, ligne 528), `_RE_RANG_SUFFIXE_STRICT` (strict, ligne 535).
- Produces: `_strip_rank_suffix_segment(valeur: str) -> str` (permissif) ; `_decoller_rang(valeur: str, motif: re.Pattern[str]) -> str` (extracteur partagé privé). `_strip_rank_suffix(valeur: str) -> str` conserve sa signature et son comportement strict.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter après le test `test_strip_rank_suffix` (juste après sa fonction, vers la ligne 421) :

```python
@pytest.mark.parametrize("brut,attendu", [
    ("2:05:29 (2)", "2:05:29"),    # rang SANS point (InterSemi finisher, 410891)
    ("33:18 (10)", "33:18"),       # rang à deux chiffres, sans point
    ("2:08:00 (1.)", "2:08:00"),   # le point reste toléré
    ("2:04:40", "2:04:40"),        # durée nue (DNF) : inchangée
    ("", ""),
])
def test_strip_rank_suffix_segment(brut, attendu):
    """#84 — variante permissive pour les cellules de segment : décolle le rang
    même sans point (`(2)`). Sûr car le pipeline segment qualifie ensuite par
    `_RE_DUREE`, filet qui n'existe pas pour le texte libre (§12.2)."""
    assert raceresult._strip_rank_suffix_segment(brut) == attendu


def test_strip_rank_suffix_segment_ne_contamine_pas_le_strict():
    """Les deux variantes restent distinctes : `_strip_rank_suffix` (nom/club/
    temps) garde sa règle stricte — un numéro d'équipe sans point survit
    (§12.2), là où la variante segment le décollerait."""
    assert raceresult._strip_rank_suffix("TCN (1)") == "TCN (1)"
    assert raceresult._strip_rank_suffix_segment("TCN (1)") == "TCN"
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `export UV_CACHE_DIR="$TMPDIR/uv-cache" && uv run pytest tests/test_raceresult.py -k strip_rank_suffix_segment -q`
Expected: FAIL — `AttributeError: module 'app.scrapers.raceresult' has no attribute '_strip_rank_suffix_segment'`.

- [ ] **Step 3: Implémenter les helpers**

Remplacer le corps de `_strip_rank_suffix` (lignes 556-577) par la version factorisée, et ajouter la variante segment. Remplacer **exactement** :

```python
def _strip_rank_suffix(valeur: str) -> str:
    """Décolle un rang suffixé (`"2:08:00 (1.)"` → `"2:08:00"`) d'une cellule.

    Toute colonne issue d'une concaténation `[X] & " (" & [X.OVERALL.P] & ")"`
    porte son rang collé de cette façon — un segment de course, mais aussi
    bien `nom`, `club` ou `temps` : le point fixe de `_peel` (C2) fait
    désormais converger vers ces rôles des expressions composées qui
    restaient opaques avant, sans garantie que leur valeur soit épargnée par
    le même motif de concaténation que les segments. Pour un segment,
    `_RE_DUREE` rejette la cellule polluée et le split est perdu ; pour
    `total_time`, `normalize_time` est permissif et laisserait passer
    `"3:18:21 (5.)"` tel quel — d'où ce décollage systématique plutôt qu'un
    relâchement de `normalize_time` ou de `_RE_DUREE`, tous deux proscrits.

    Utilise `_RE_RANG_SUFFIXE_STRICT` (point final exigé), pas
    `_RE_RANG_SUFFIXE` : `nom` et `club` sont du texte libre où une parenthèse
    finale sans point est un contenu légitime (code départemental, numéro
    d'équipe de relais), à la différence de `sexe`/`categorie` (vocabulaire
    fermé, traités par `_split_rank_category`) où l'ambiguïté n'existe pas.
    """
    trouve = _RE_RANG_SUFFIXE_STRICT.match(valeur)
    return trouve.group(1).strip() if trouve else valeur
```

par :

```python
def _decoller_rang(valeur: str, motif: re.Pattern[str]) -> str:
    """Retire le rang parenthésé reconnu par `motif`, ou rend `valeur` intacte."""
    trouve = motif.match(valeur)
    return trouve.group(1).strip() if trouve else valeur


def _strip_rank_suffix(valeur: str) -> str:
    """Décolle un rang suffixé (`"2:08:00 (1.)"` → `"2:08:00"`) d'une cellule.

    Toute colonne issue d'une concaténation `[X] & " (" & [X.OVERALL.P] & ")"`
    porte son rang collé de cette façon — un segment de course, mais aussi
    bien `nom`, `club` ou `temps` : le point fixe de `_peel` (C2) fait
    désormais converger vers ces rôles des expressions composées qui
    restaient opaques avant, sans garantie que leur valeur soit épargnée par
    le même motif de concaténation que les segments. Pour un segment,
    `_RE_DUREE` rejette la cellule polluée et le split est perdu ; pour
    `total_time`, `normalize_time` est permissif et laisserait passer
    `"3:18:21 (5.)"` tel quel — d'où ce décollage systématique plutôt qu'un
    relâchement de `normalize_time` ou de `_RE_DUREE`, tous deux proscrits.

    Utilise `_RE_RANG_SUFFIXE_STRICT` (point final exigé), pas
    `_RE_RANG_SUFFIXE` : `nom` et `club` sont du texte libre où une parenthèse
    finale sans point est un contenu légitime (code départemental, numéro
    d'équipe de relais), à la différence de `sexe`/`categorie` (vocabulaire
    fermé, traités par `_split_rank_category`) où l'ambiguïté n'existe pas.
    Les cellules de segment relèvent, elles, de `_strip_rank_suffix_segment`.
    """
    return _decoller_rang(valeur, _RE_RANG_SUFFIXE_STRICT)


def _strip_rank_suffix_segment(valeur: str) -> str:
    """Variante permissive (point facultatif) pour les cellules de SEGMENT.

    RaceResult suffixe le rang intermédiaire aux seuls finishers et **sans
    point** (`iif([STATUS]=0 …;" (" & [InterSemi.OVERALL] & ")")`). La variante
    stricte laisse alors passer `"2:05:29 (2)"`, que `_RE_DUREE` rejette
    ensuite : le split du finisher est perdu, tandis qu'un non-finisher (durée
    nue) fuit — incohérence documentée en verrou C (issue #84, §4.2 du sondage).

    Le permissif est sûr *ici seulement* parce que le pipeline segment garde la
    valeur décollée par `_RE_DUREE`. L'ambiguïté qui interdit le permissif sur
    `nom`/`club`/`temps` (§12.2 : `"TCN (1)"` fusionnerait deux équipes)
    n'existe pas pour une durée — `"TCN (1)"` décollé donne `"TCN"`, que
    `_RE_DUREE` rejette. Aucune durée légitime ne finit par une parenthèse qui
    ne soit pas un rang : stricte pour le texte libre, permissive pour les
    durées gardées.
    """
    return _decoller_rang(valeur, _RE_RANG_SUFFIXE)
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `export UV_CACHE_DIR="$TMPDIR/uv-cache" && uv run pytest tests/test_raceresult.py -k "strip_rank_suffix" -q`
Expected: PASS (les nouveaux tests + l'existant `test_strip_rank_suffix` toujours verts).

- [ ] **Step 5: Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "feat(raceresult): décollage permissif du rang pour les cellules de segment (#84)"
```

---

### Task 2: Le pipeline segment emploie la variante permissive

**Files:**
- Modify: `backend/app/scrapers/raceresult.py:1075-1087` (compréhension `r.segments` + commentaire)
- Test: `backend/tests/test_raceresult.py` (après `test_build_result_decolle_le_rang_suffixe_dune_valeur_de_segment`)

**Interfaces:**
- Consumes: `_strip_rank_suffix_segment` (Task 1), `_map_columns`, `_build_result`, `_RE_DUREE`.
- Produces: aucun symbole nouveau ; change le comportement de `_build_result` sur les cellules de segment à rang sans point.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter après `test_build_result_decolle_le_rang_suffixe_dune_valeur_de_segment` :

```python
def test_build_result_recupere_un_segment_au_rang_suffixe_sans_point():
    """#84, cœur du correctif : une cellule de segment portant un rang SANS
    point (`'2:05:29 (2)'`, forme InterSemi des finishers 410891) est décollée
    par la variante permissive puis qualifiée par `_RE_DUREE` — le split est
    récupéré, là où la variante stricte le laissait rejeter."""
    expr = '[Vélo] & " (" & [Vélo.OVERALL.P] & ")"'
    payload = {
        "DataFields": ["BIB", "ID", expr],
        "list": {"Fields": [{"Expression": expr, "Label": "Vélo"}]},
    }
    roles, segments, extras = raceresult._map_columns(payload)

    r = raceresult._build_result(
        ["810", "494", "2:05:29 (2)"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )

    assert r.segments == [("Vélo", "02:05:29")]


def test_build_result_permissif_segment_reste_garde_par_re_duree():
    """Filet de sûreté du permissif : décoller `(2)` d'un contenu non-durée
    (`'TCN (2)'`) donne `'TCN'`, rejeté par `_RE_DUREE` — aucun faux split.
    C'est ce qui rend le permissif sans danger sur les segments, à la
    différence du texte libre (§12.2)."""
    expr = '[Vélo] & " (" & [Vélo.OVERALL.P] & ")"'
    payload = {
        "DataFields": ["BIB", "ID", expr],
        "list": {"Fields": [{"Expression": expr, "Label": "Vélo"}]},
    }
    roles, segments, extras = raceresult._map_columns(payload)

    r = raceresult._build_result(
        ["1", "1", "TCN (2)"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )

    assert r.segments is None
```

- [ ] **Step 2: Lancer les tests, vérifier l'échec**

Run: `export UV_CACHE_DIR="$TMPDIR/uv-cache" && uv run pytest tests/test_raceresult.py -k "recupere_un_segment_au_rang_suffixe_sans_point or permissif_segment_reste_garde" -q`
Expected: FAIL sur `test_build_result_recupere_un_segment_au_rang_suffixe_sans_point` — `r.segments is None` (la variante stricte n'a pas décollé `(2)`, `_RE_DUREE` a rejeté). Le second test passe déjà (par coïncidence : la stricte ne décolle pas non plus). C'est le premier qui pilote le changement.

- [ ] **Step 3: Basculer le pipeline sur la variante permissive**

Dans la compréhension `r.segments` (lignes 1075-1087), remplacer le commentaire et l'appel. Remplacer **exactement** :

```python
    # Une colonne candidate ne devient un segment que si sa valeur est bien une
    # durée : c'est ce qui écarte les colonnes « Tours » ou « Distance », dont
    # l'expression est un token simple indiscernable de celle d'un split. Le
    # rang suffixé (`"33:18 (10.)"`) est décollé AVANT cette qualification :
    # `_RE_DUREE` le rejetterait tel quel et ferait perdre le split entier.
    r.segments = [
        (label, normalize_time(valeur))
        for label, col in segments
        if col < len(ligne)
        and (cellule_brute := _clean_cell(ligne[col]))
        and (valeur := _strip_rank_suffix(cellule_brute))
        and _RE_DUREE.match(valeur)
    ] or None
```

par :

```python
    # Une colonne candidate ne devient un segment que si sa valeur est bien une
    # durée : c'est ce qui écarte les colonnes « Tours » ou « Distance », dont
    # l'expression est un token simple indiscernable de celle d'un split. Le
    # rang suffixé est décollé AVANT cette qualification (`_RE_DUREE` le
    # rejetterait tel quel et ferait perdre le split entier), avec la variante
    # PERMISSIVE (`_strip_rank_suffix_segment`, point facultatif) : RaceResult
    # suffixe l'intermédiaire des finishers sans point (`"2:05:29 (2)"`) et
    # laisse la durée nue aux non-finishers — sans le permissif, seul le
    # non-finisher fuyait (verrou C, #84). Le permissif est sûr ici, car
    # `_RE_DUREE` en aval rejette tout ce qui n'est pas une durée.
    r.segments = [
        (label, normalize_time(valeur))
        for label, col in segments
        if col < len(ligne)
        and (cellule_brute := _clean_cell(ligne[col]))
        and (valeur := _strip_rank_suffix_segment(cellule_brute))
        and _RE_DUREE.match(valeur)
    ] or None
```

- [ ] **Step 4: Lancer les tests, vérifier le succès**

Run: `export UV_CACHE_DIR="$TMPDIR/uv-cache" && uv run pytest tests/test_raceresult.py -k "build_result" -q`
Expected: PASS (dont les deux nouveaux et les non-régressions `test_build_result_decolle_le_rang_suffixe_dune_valeur_de_segment`, `..._recupere_les_segments_malgre_la_concatenation_imbriquee`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/scrapers/raceresult.py backend/tests/test_raceresult.py
git commit -m "feat(raceresult): récupérer les splits de segment des finishers (verrou C, #84)"
```

---

### Task 3: Mettre à jour le test de non-régression 410891

**Files:**
- Modify: `backend/tests/test_raceresult.py:2680` (`test_scrape_event_all_410891_hidden_fuite_un_split_pour_un_dnf`)

**Interfaces:**
- Consumes: `_monte_pipeline_fixtures`, fixtures `410891_*.json` (inchangées), `raceresult.scrape_event_all`.
- Produces: test renommé `test_scrape_event_all_410891_hidden_recupere_les_splits_intermediaires`.

- [ ] **Step 1: Réécrire le test (il échoue avant relecture visuelle)**

Remplacer intégralement la fonction `test_scrape_event_all_410891_hidden_fuite_un_split_pour_un_dnf` (docstring comprise) par :

```python
def test_scrape_event_all_410891_hidden_recupere_les_splits_intermediaires(monkeypatch):
    """#84 : la colonne de split intermédiaire (`InterSemi`) suffixe le rang aux
    finishers SANS point (`'2:05:29 (2)'`) et laisse la durée nue aux
    non-finishers (`'2:04:40'`). Le pipeline segment décolle désormais le rang
    même sans point (variante permissive, gardée par `_RE_DUREE`) : les 111
    splits réels sont récupérés — 110 finishers + le DNF 804 — là où seul le
    DNF nu fuyait (verrou C, différé par #60, fermé pour les segments ici)."""
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
    assert len(res) == 122, "aucun participant ajouté par le hidden (inscrits ignorés)"
    avec_splits = [r for r in res if r.segments]
    assert len(avec_splits) == 111, "110 finishers décorés + le DNF nu"
    # Le DNF conserve son intermédiaire (franchi avant l'abandon) : le nettoyage
    # #60 vide temps/rangs des non-finishers, jamais les segments.
    dnf = next(r for r in res if r.bib_number == "804")  # PRAUD Samuel, DNF
    assert dnf.segments == [("10KMS", "02:04:40")]
    # Un finisher récupère aussi son split, ex-rejeté par le verrou C.
    finisher = next(r for r in res if r.bib_number == "810")  # RONDEAU David
    assert finisher.segments == [("10KMS", "02:05:29")]
```

- [ ] **Step 2: Lancer le test**

Run: `export UV_CACHE_DIR="$TMPDIR/uv-cache" && uv run pytest tests/test_raceresult.py -k "410891_hidden_recupere" -q`
Expected: PASS. **Si le compte diffère de 111** : ne pas ajuster l'assertion à l'aveugle — inspecter (systematic-debugging) quelles lignes du groupe `inter` n'ont pas de segment (cellule vide vs non appariée à un participant publié). Le §4.2 mesure 111 (110 décorés + 1 nu, 11 vides sur 122).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_raceresult.py
git commit -m "test(raceresult): 410891 récupère 111 splits intermédiaires (verrou C, #84)"
```

---

### Task 4: Amender la documentation (sondage §4.2 et §12.2)

**Files:**
- Modify: `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md` (fin de §4.2 ; fin de §12.2)

**Interfaces:** documentation seule, aucun code.

- [ ] **Step 1: Amender §4.2**

Après la ligne `Design : `2026-07-23-raceresult-listes-hidden-design.md`.` (fin du §4.2), ajouter :

```markdown

**(amendement 2026-07-23, issue #84 — verrou C fermé pour les segments)** : le
pipeline segment décolle désormais le rang suffixé **même sans point**
(`_strip_rank_suffix_segment`, variante permissive de §12.2), cantonné aux
cellules de segment car `_RE_DUREE` les garde en aval. Mesuré sur 410891 : les
**111 splits réels** (110 finishers décorés `'2:05:29 (2)'` + le DNF nu 804) sont
récupérés, l'incohérence « le DNF porte plus de données que les finishers »
disparaît par récupération. `_strip_rank_suffix` (strict) reste inchangé pour
`nom`/`club`/`temps`. Design : `2026-07-23-raceresult-verrou-c-segments-design.md`.
```

- [ ] **Step 2: Amender §12.2**

Après la ligne `La règle permissive reste employée pour `sexe` et `categorie`, dont les` / `vocabulaires sont fermés.` (fin du §12.2), ajouter :

```markdown

**(amendement 2026-07-23, issue #84)** : la règle permissive s'étend aussi aux
cellules de **segment** (`_strip_rank_suffix_segment`). Non par relâchement de
l'arbitrage, mais par délimitation de sa portée : le point n'est exigé que sur
le **texte libre** (`nom`/`club`/`temps`), où `'TCN (1)'` doit survivre. Sur une
**durée**, une parenthèse finale ne peut être qu'un rang, et `_RE_DUREE` garde
la valeur décollée — le faux positif redouté (`'TCN'`) est rejeté sans dégât.
Stricte pour le texte libre, permissive pour les durées gardées.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md
git commit -m "docs(raceresult): §4.2/§12.2 — verrou C fermé pour les segments (#84)"
```

---

### Task 5: Vérification finale (suite complète + lint)

**Files:** aucun (validation).

- [ ] **Step 1: Suite raceresult + suite unitaire complète**

Run: `export UV_CACHE_DIR="$TMPDIR/uv-cache" && uv run pytest tests/test_raceresult.py -q && uv run pytest -m "not integration" -q`
Expected: tout vert (aucune régression ; le décompte de tests raceresult augmente de 4 nouveaux).

- [ ] **Step 2: Lint**

Run: `export UV_CACHE_DIR="$TMPDIR/uv-cache" && uv run ruff check app/scrapers/raceresult.py tests/test_raceresult.py`
Expected: `All checks passed!`

- [ ] **Step 3: Revue de complétude**

Vérifier : `_strip_rank_suffix` (strict) toujours utilisé pour `nom`/`club`/`temps` (grep) ; `_RE_DUREE`/`normalize_time` inchangés (`git diff` ne les touche pas).

Run: `git diff --stat main...HEAD`

## Self-Review

- **Couverture spec** : helper permissif (Task 1), usage pipeline + garde `_RE_DUREE` (Task 2), non-régression 410891 → 111 (Task 3), amendements §4.2/§12.2 (Task 4), non-régression du strict et de `_RE_DUREE` (Task 1 step 1, Task 5). §12.1 et hidden : hors périmètre, non touchés. ✅
- **Placeholders** : aucun ; tout le code est fourni verbatim.
- **Cohérence des types** : `_decoller_rang(valeur: str, motif: re.Pattern[str]) -> str`, `_strip_rank_suffix_segment(valeur: str) -> str` cohérents entre Task 1 (def) et Task 2 (appel dans la compréhension). Label segment `"10KMS"` cohérent Task 3.

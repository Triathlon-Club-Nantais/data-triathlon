"""
Tests unitaires pour scrapers/raceresult.py (sans réseau).

Fixtures réduites à la main, provenance et date en tête de chaque fichier.
Les appels HTTP passent par un faux client httpx (pattern test_sportinnovation.py)
ou par monkeypatch des helpers `_fetch_*` (pattern test_wiclax.py).
"""
import json
import logging
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import raceresult, registry
from app.scrapers.base import STATUS_DNF, STATUS_DNS, ScrapedResult

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


class _FauxClient:
    """Client httpx minimal : sert des réponses par sous-chaîne d'URL.

    `routes` mappe un fragment d'URL vers (status_code, texte). Une URL sans
    route déclarée lève, pour qu'un appel réseau inattendu casse le test au lieu
    de passer silencieusement.

    `appels` enregistre l'URL **effective**, `params=` fusionné dans la query :
    le code de production reste libre de passer ses paramètres comme httpx
    l'attend, sans devoir les concaténer à la main pour être observable.
    """

    def __init__(self, routes: dict[str, tuple[int, str]]):
        self.routes = routes
        self.appels: list[str] = []

    def get(self, url: str, **kwargs) -> httpx.Response:
        params = kwargs.get("params")
        self.appels.append(str(httpx.URL(url, params=params)) if params else url)
        for fragment, (status, texte) in self.routes.items():
            if fragment in url:
                return httpx.Response(
                    status, text=texte, request=httpx.Request("GET", url)
                )
        raise AssertionError(f"URL non routée dans le faux client : {url}")


# ── Routage ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://my.raceresult.com/399938/results",
    "https://my3.raceresult.com/393893/",
    "https://www.espace-competition.com/index.php?page=resultats&comp_uid=3178",
    "https://www.chronoconsult.fr/result/triathlon-de-roanne-villerest/",
])
def test_routage_vers_raceresult(url):
    assert registry.detect_provider(url) == "raceresult"


@pytest.mark.parametrize("url", [
    "https://evilraceresult.com/399938/results",
    "https://raceresult.com.attaquant.net/399938/",
    "https://www.klikego.com/resultats/x/1",
])
def test_hosts_sosies_non_captes(url):
    assert registry.detect_provider(url) != "raceresult"


# ── Résolution de l'eventId ──────────────────────────────────────────────────

def test_event_id_depuis_le_path_sans_requete():
    client = _FauxClient({})
    assert raceresult._resolve_event_id(
        "https://my.raceresult.com/399938/results", client
    ) == "399938"
    assert client.appels == [], "aucune requête ne doit partir pour un host RaceResult"


def test_event_id_depuis_la_facade_chronoconsult():
    """L'id vient de `new RRPublish(el, 399938, …)`, pas de `comp_uid`."""
    client = _FauxClient({
        "chronoconsult.fr": (200, _fixture("chronoconsult_result_page.html")),
    })
    url = "https://www.chronoconsult.fr/result/triathlon-de-roanne-villerest/"

    assert raceresult._resolve_event_id(url, client) == "399938"


def test_event_id_depuis_la_facade_espace_competition():
    """C-D, second volet : espace-competition.com sert l'identifiant NU, quand
    chronoconsult.fr le sert entre guillemets. Les deux fixtures sont des
    captures réelles du 2026-07-19 ; l'expression rationnelle doit accepter les
    deux formes, faute de quoi une façade entière devient inexploitable."""
    client = _FauxClient({
        "espace-competition.com": (200, _fixture("espace_competition_result_page.html")),
    })
    url = "https://www.espace-competition.com/index.php?module=sportif&action=resultat&comp_uid=3205"

    assert raceresult._resolve_event_id(url, client) == "411749"


def test_event_id_repli_sur_le_logo():
    """Sans appel RRPublish lisible, le lien `/api/logo` porte le même id."""
    html = '<html><body><img src="https://my.raceresult.com/406844/api/logo"></body></html>'
    client = _FauxClient({"espace-competition.com": (200, html)})
    url = "https://www.espace-competition.com/index.php?page=resultats&comp_uid=3178"

    assert raceresult._resolve_event_id(url, client) == "406844"


def test_event_id_introuvable_leve_value_error():
    client = _FauxClient({"espace-competition.com": (200, "<html><body>rien</body></html>")})
    url = "https://www.espace-competition.com/index.php?comp_uid=3178"

    with pytest.raises(ValueError, match="espace-competition.com"):
        raceresult._resolve_event_id(url, client)


def test_base_api_unique_quel_que_soit_le_host():
    """C-A/§2 du sondage : l'apex `my.raceresult.com` sert les 9 épreuves du
    panel, y compris celles que l'interface héberge sur my2/my3/my4. Il n'y a
    donc plus de résolution de serveur — une seule constante."""
    assert raceresult._API_BASE == "https://my.raceresult.com"


# ── Métadonnées (JSON-LD) et configuration ──────────────────────────────────

def test_fetch_meta_lit_le_json_ld():
    client = _FauxClient({"/results": (200, _fixture("raceresult_page_meta.html"))})

    nom, jour, ville = raceresult._fetch_meta("399938", client)

    assert nom == "Triathlon de Roanne Villerest"
    assert jour == date(2026, 6, 18)
    assert ville == "SAINT-HERBLAIN"


def test_fetch_meta_sans_json_ld_ne_leve_pas():
    """Une page sans JSON-LD dégrade proprement : l'épreuve reste importable."""
    client = _FauxClient({"/results": (200, "<html><body>vide</body></html>")})

    assert raceresult._fetch_meta("1", client) == ("", None, "")


def test_fetch_config_interroge_la_route_canonique():
    """C-A : `/{id}/RRPublish/data/config` est un alias hérité qui répond 404 sur
    toute épreuve de la saison en cours. Seule `/{id}/results/config` est
    générale — le faux client ne route QUE celle-ci, donc un retour à l'alias
    fait échouer ce test au lieu de passer inaperçu."""
    client = _FauxClient({
        "/results/config": (200, _fixture("raceresult_config_rumilly.json")),
    })

    config = raceresult._fetch_config("393893", client)

    assert config["key"] == "0149954ef060e08fce32a6ea646cf880"
    assert config["contests"] == {
        "1": "Distance XS",
        "2": "Distance Jeunes - Poussin, Pupille",
        "3": "Half Iron du Semnoz",
        "4": "Distance M",
    }
    assert "page=results" in client.appels[0]
    assert "/393893/results/config" in client.appels[0]
    assert "RRPublish/data" not in client.appels[0]


def test_iter_list_specs_lit_tabconfig_lists():
    """C-B : sur la route canonique `config["lists"]` vaut `null` — les listes
    vivent sous `TabConfig.Lists`, un tableau plat d'une entrée par couple
    (liste, contest), le contest étant **explicite**. Fixture : capture réelle de
    l'event 393893 le 2026-07-19."""
    config = json.loads(_fixture("raceresult_config_rumilly.json"))

    assert config["lists"] is None, "la route canonique ne sert rien sous `lists`"
    assert raceresult._iter_list_specs(config) == [
        ("04 - Classements|Classement général", "3"),
        ("04 - Classements|Classement général", "4"),
        ("04 - Classements|Classement général", "1"),
        ("04 - Classements|Classement général Jeunes", "2"),
    ]


def test_iter_list_specs_ecarte_les_listes_hidden():
    """Le discriminant est `Mode == "hidden"` : les listes d'affichage et les
    listes d'inscrits y sont marquées, les classements publiés non."""
    config = {"TabConfig": {"Lists": [
        {"Name": "Affichage live", "Contest": "1", "Mode": "hidden"},
        {"Name": "Classement", "Contest": "1", "Mode": ""},
        {"Name": "Classement sans champ Mode", "Contest": "2"},
    ]}}

    assert raceresult._iter_list_specs(config) == [
        ("Classement", "1"),
        ("Classement sans champ Mode", "2"),
    ]


def test_iter_list_specs_ne_filtre_pas_sur_live():
    """C-C, non-régression. Le critère `Live` avait été calibré sur une seule
    épreuve, où il coïncidait avec `Mode`. Sur l'event 405100, les 10 listes
    portent `Live: 1` — y compris les 3 vrais classements : filtrer sur `Live`
    y vide l'épreuve entière. Fixture : capture réelle du 2026-07-19."""
    config = json.loads(_fixture("raceresult_config_foulee.json"))
    toutes = config["TabConfig"]["Lists"]

    assert len(toutes) == 10
    assert all(e["Live"] == 1 for e in toutes), "prémisse de la fixture"

    specs = raceresult._iter_list_specs(config)

    assert specs == [
        ("1-CHRONO|Class génél", "1"),
        ("1-CHRONO|Class génél", "2"),
        ("1-CHRONO|Class génél", "3"),
    ]
    assert {c for _n, c in specs} == set(config["contests"]), (
        "les listes publiées doivent couvrir tous les contests annoncés"
    )


def test_iter_list_specs_leve_sur_une_forme_inattendue():
    """Une config sans `TabConfig.Lists` exploitable lève bruyamment : c'est le
    symptôme exact d'une interrogation de la route héritée, qui doit se voir
    plutôt que de produire une épreuve silencieusement vide."""
    with pytest.raises(ValueError, match="TabConfig.Lists de forme inattendue"):
        raceresult._iter_list_specs({"lists": [{"Name": "X", "Contest": "0"}]})


# ── Mapping des colonnes ─────────────────────────────────────────────────────

def _payload_rumilly() -> dict:
    return json.loads(_fixture("raceresult_list_rumilly_m.json"))


def _champs_rumilly() -> dict:
    """`DataFields` + `Fields` de la fixture Rumilly — `Fields` vit sous `list`
    (forme réelle observée en production, cf. `_map_columns`)."""
    payload = _payload_rumilly()
    return {
        "DataFields": payload["DataFields"],
        "list": {"Fields": payload["list"]["Fields"]},
    }


@pytest.mark.parametrize("expr,attendu", [
    ("OuStatut([ClassementGénéral.P])", "classementgeneral.p"),
    ("ucase([CLUB])", "club"),
    ("AfficherNom", "affichernom"),
    ("[Course.OVERALL.P] ", "course.overall.p"),
    ("TIME", "time"),
    ("#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]", "classementcategorie.pagegroup.nameshort"),
])
def test_peel(expr, attendu):
    assert raceresult._peel(expr) == attendu


# ── C2 : point fixe de `_peel` (concaténation imbriquée dans un `if(…)`) ────
# Capture réelle du 2026-07-19 sur l'épreuve 401699 (Half Iron du Lac
# d'Annecy, colonne Vélo) : `docs/superpowers/specs/2026-07-19-raceresult-api-
# sondage.md` ne couvrait pas ce cas, seul le sondage de cette épreuve l'a
# révélé (0 segment sur 587 participants avant correctif).

def test_peel_point_fixe_concatenation_imbriquee_dans_if():
    """Une seule passe ordonnée s'arrête à la conditionnelle défaite —
    `if([STATUS]<>2;[Vélo] & " (" & [Vélo.OVERALL.P] & ")")` devient
    `[Vélo] & " (" & [Vélo.OVERALL.P] & ")"` — sans rejouer l'étape de
    concaténation, qui n'était visible qu'une fois l'enrobage `if(…)` retiré.
    Le peel restait une expression composée, jamais reconnue comme le token
    simple d'un segment."""
    expr = 'if([STATUS]<>2;[Vélo] & " (" & [Vélo.OVERALL.P] & ")")'
    assert raceresult._peel(expr) == "velo"


def test_peel_concatenation_non_imbriquee_deja_correcte():
    """Non-régression : la même colonne, sur la liste Relais de la même
    épreuve, n'est pas enveloppée dans un `if(…)` — elle pelait déjà
    correctement avant C2 (cf. le sondage du brief), la boucle de point fixe
    ne doit pas la casser."""
    expr = '[Vélo] & " (" & [Vélo.OVERALL.P] & ")"'
    assert raceresult._peel(expr) == "velo"


def _nidifier_if_status(n: int, coeur: str = "[Vélo]") -> str:
    """`n` enveloppes `if([STATUS]<>2;…)` autour de `coeur` — la forme réelle
    de production (contrairement à un `if(1;…)` littéral, dont la condition ne
    comporte aucun opérateur de comparaison et n'exerce donc jamais
    `_RE_COMPARAISON`)."""
    s = coeur
    for _ in range(n):
        s = f"if([STATUS]<>2;{s})"
    return s


def test_peel_converge_au_dela_des_niveaux_observes_en_production():
    """Le point fixe (pas le repli `max(len)`) résout une imbrication plus
    profonde que celle observée en production (2 niveaux) : chaque enveloppe
    porte une vraie condition `[STATUS]<>2`, donc chaque tour élimine le terme
    qui compare via `_RE_COMPARAISON` — pas via la longueur."""
    expr = _nidifier_if_status(4)
    assert raceresult._peel(expr) == "velo"


def test_peel_borne_par_peel_max_iterations_au_dela_du_point_fixe(caplog):
    """`_peel` est réellement borné par `_PEEL_MAX_ITERATIONS`, pas seulement
    par le point fixe : chaque enveloppe `if([STATUS]<>2;…)` ne se défait que
    d'un niveau par tour (l'enrobage `if(…)` puis la conditionnelle `;`
    exposent le niveau suivant, mais pas plus), donc une imbrication de plus
    de `_PEEL_MAX_ITERATIONS` niveaux n'a pas fini de converger quand la
    boucle s'arrête — `_peel` rend alors une chaîne partiellement pelée, sans
    lever, et le signale via `logger.debug` (cf. Mineur 3)."""
    profondeur = raceresult._PEEL_MAX_ITERATIONS + 1
    expr = _nidifier_if_status(profondeur)

    # Handler attaché directement au logger du module plutôt que de compter
    # sur la propagation vers le root logger : `setup_logging()` (appelé par
    # tout test qui importe `app.main`) vide les handlers du root logger, ce
    # qui désactiverait `caplog` s'il ne s'y accrochait que par propagation.
    # `.disabled` est remis à `False` explicitement : dans la suite complète,
    # `test_migrations.py` déclenche `alembic/env.py`, dont le `fileConfig()`
    # désactive silencieusement tout logger déjà enregistré (`disable_existing_
    # loggers=True` par défaut, hors périmètre de ce correctif) — sans ce reset
    # local, ce test devient un faux négatif d'ordre d'exécution plutôt qu'une
    # preuve sur `_peel`. Le niveau est restauré pour la même raison : sans
    # cela, le passage à DEBUG fuite sur le reste de la suite (Mineur 4).
    logger_etat = raceresult.logger.disabled
    niveau_etat = raceresult.logger.level
    raceresult.logger.disabled = False
    raceresult.logger.addHandler(caplog.handler)
    raceresult.logger.setLevel(logging.DEBUG)
    try:
        resultat = raceresult._peel(expr)
    finally:
        raceresult.logger.removeHandler(caplog.handler)
        raceresult.logger.disabled = logger_etat
        raceresult.logger.setLevel(niveau_etat)

    assert resultat != "velo", "une imbrication de plus de 10 niveaux ne doit pas converger"
    # Pas d'assertion sur la forme exacte du résidu partiellement pelé
    # (Mineur 5) : elle figerait la forme cosmétique du nettoyage final
    # (`replace("[", "")`, `translate(_ACCENTS)`) sans rien prouver de plus
    # que `resultat != "velo"` ci-dessus — c'est la non-convergence qui
    # importe, pas la chaîne précise sur laquelle `_peel` s'arrête.
    assert "n'a pas convergé" in caplog.text


# ── C3 : rang collé sur une valeur de segment ───────────────────────────────
#
# Important 2 (revue du correctif Important 1) : les cas ci-dessous couvrent
# deux familles distinctes, à parité — pas seulement « pousser une valeur
# polluée et vérifier qu'elle est nettoyée ». La seconde famille pratique le
# test symétrique qui manquait : pousser une valeur légitime portant des
# parenthèses de texte libre et vérifier qu'elle SURVIT intacte. Sans ce
# second axe, une regex trop permissive (motif d'origine, point facultatif)
# passe la suite tout en amputant `"TCN (1)"` en `"TCN"` — deux équipes de
# relais fusionnées sous un même nom.
@pytest.mark.parametrize("brut,attendu", [
    # -- rang collé, doit être décollé --
    ("2:08:00 (1.)", "2:08:00"),   # capture réelle 401699, colonne Vélo
    ("33:18 (10.)", "33:18"),      # capture réelle 401699, colonne Nat. + T1
    ("35:28", "35:28"),            # pas de rang collé : inchangée
    ("", ""),
    # -- texte libre légitime portant des parenthèses, doit survivre intact --
    ("TCN (44)", "TCN (44)"),                        # code départemental
    ("PAYS DE GEX NATATION (PGN)", "PAYS DE GEX NATATION (PGN)"),  # sigle
    ("TCN (1)", "TCN (1)"),                           # numéro d'équipe de relais
    ("TCN (2)", "TCN (2)"),                           # équipe distincte de la précédente
])
def test_strip_rank_suffix(brut, attendu):
    assert raceresult._strip_rank_suffix(brut) == attendu


@pytest.mark.parametrize("label,attendu", [
    ("{DE:Startnr|EN:Bib|FR:Dos.}", "Dos."),
    ("{DE:Zeit|EN:Time}", "Time"),
    ("{DE:X}", "X"),
    ("Nat.", "Nat."),
    ("", ""),
    # Formes réelles du panel, toujours reconnues après le resserrement de la
    # règle : la sévérité vise le texte libre, pas les libellés de l'outil.
    ("{FR:Nat.|EN:Team}", "Nat."),
    ("{EN:Gender|DE:M/W|FR:Sexe}", "Sexe"),
    ("{EN:Rank|DE:Pl.|FR:Rank}", "Rank"),
    # Une variante vide n'est pas retenue : on descend à la suivante.
    ("{DE:|EN:Time}", "Time"),
    # La valeur peut contenir un deux-points ; seule la première coupure compte.
    ("{FR:10:30}", "10:30"),
])
def test_label_i18n(label, attendu):
    """Mineur : les listes d'affichage encodent leurs libellés en `{DE:…|EN:…|
    FR:…}` — sans normalisation, ce brut atterrit tel quel comme clé JSON de
    `segments`. Priorité au français, repli sur l'anglais."""
    assert raceresult._label_i18n(label) == attendu


@pytest.mark.parametrize("brut,attendu", [
    ("  2.  ", "2."),
    ("[img:https://my.raceresult.com/flag.png]FRA", "FRA"),
    ('#79', "79"),
    (None, ""),
    (42, "42"),
])
def test_clean_cell(brut, attendu):
    assert raceresult._clean_cell(brut) == attendu


@pytest.mark.parametrize("brut,attendu", [
    ("{EN:Men|FR:Masculin}", "Masculin"),
    ("{EN:Mixed|FR:Mixte}", "Mixte"),
    ("{EN:Women|FR:Féminin}", "Féminin"),
    # Repli anglais quand le français manque, comme pour les libellés.
    ("{DE:Männer|EN:Men}", "Men"),
])
def test_clean_cell_retire_l_enrobage_i18n_des_valeurs(brut, attendu):
    """I1 — l'enrobage i18n ne décore pas que les libellés, il voyage aussi dans
    les **valeurs**.

    Mesuré sur l'event 401699 : ses 33 cellules de catégorie relais entraient en
    base telles quelles (`category = '{EN:Men|FR:Masculin}'`), illisibles en UI
    et non regroupables. `_label_i18n` existait déjà mais n'était appliqué qu'à
    la construction des libellés de colonne.
    """
    assert raceresult._clean_cell(brut) == attendu


@pytest.mark.parametrize("valeur", [
    # Le témoin réel du panel : une accolade parasite dans un nom saisi à la
    # main (event 411749). Elle n'ouvre ni ne ferme un enrobage complet.
    "ROBERT Julie}",
    "{ALEX",
    # Une barre verticale hors accolades n'est pas un séparateur de variantes.
    "TCN | Section triathlon",
    # Enrobage complet mais sans variante `LANGUE:valeur` : rien à choisir, donc
    # rien à retirer — sans quoi la valeur disparaîtrait.
    "{équipe}",
    "{}",
    # Une variante ne doit pas être devinée sur une accolade non fermée.
    "{FR:Masculin",
    # --- Axe « clé de langue » : la partie gauche n'est pas un code de langue,
    # c'est du texte. La prendre pour une clé jetait le sens de la cellule.
    "{Team: Bleu}",
    "{ATTENTION: dossard 12}",
    "{Equipe:Les Bleus}",
    # Clés de 3 lettres : la longueur est fixée à 2 (ISO 639-1, et les 266 clés
    # du panel), sans quoi ces deux cellules seraient amputées en silence.
    "{Nom:Dupont}",
    "{Cat:S4M}",
    # --- Axe « accolade interne » : deux enrobages accolés ne forment pas un
    # enrobage unique. Un `.*` gourmand rendait ici `"1} et {B:2"`.
    "{A:1} et {B:2}",
    "{FR:Bleu} / {FR:Rouge}",
    # --- Axe « toutes les parties bien formées » : une partie de texte libre
    # désarme la reconnaissance plutôt que de faire jeter le reste.
    "{FR:Masculin|à confirmer}",
    # --- Axe « variante vide » : vider une cellule en silence est le pire des
    # résultats, rien en aval ne peut le rattraper.
    "{FR:}",
    "{FR:|EN:}",
])
def test_clean_cell_laisse_intacte_une_valeur_legitime(valeur):
    """I1, sens inverse : `_clean_cell` est sur le chemin de **toutes** les
    cellules — donc de champs de texte libre saisis par des organisateurs, où un
    deux-points, une accolade ou un `|` sont banals. La garde doit laisser
    passer tout ce qui n'est pas un enrobage i18n.

    Les quatre derniers groupes couvrent les quatre axes de sévérité de la
    reconnaissance (clé de langue, accolade interne, parties toutes bien
    formées, variante non vide). Chacun correspond à une corruption
    effectivement produite par une reconnaissance lâche `^\\{(.*)\\}$` :
    `'{Team: Bleu}'` → `' Bleu'`, `'{A:1} et {B:2}'` → `'1} et {B:2'`,
    `'{FR:}'` → `''`.

    Aucun de ces axes n'est exercé par le panel — c'est précisément pourquoi ils
    sont ici : le resserrement ne déplace rien sur les 17 épreuves capturées
    (0 écart mesuré sur 176 691 cellules et 834 libellés), il ne protège que des
    formes non observées.
    """
    assert raceresult._clean_cell(valeur) == valeur


@pytest.mark.parametrize("cell,attendu", [
    ("1.S4M", (1, "S4M")),
    ("12.V1M", (12, "V1M")),
    ("S3F", (None, "S3F")),
    ("", (None, "")),
])
def test_split_rank_category(cell, attendu):
    assert raceresult._split_rank_category(cell) == attendu


def test_map_columns_utilise_l_index_de_datafields():
    """Le décalage BIB/ID rend la position dans `Fields` inutilisable telle quelle."""
    roles, segments, extras = raceresult._map_columns(_payload_rumilly())

    assert roles["bib"] == 0          # DataFields[0] est toujours BIB
    assert roles["rang"] == 2         # Fields[0], mais DataFields[2]
    assert roles["nom"] == 4
    assert roles["sexe"] == 5
    assert roles["rang_categorie"] == 6
    assert roles["club"] == 7
    assert roles["temps"] == 18


def test_map_columns_rejette_les_colonnes_de_rang_de_split():
    """`[Natation.OVERALL.P]` vaut "2." — c'est un rang, pas le temps de natation."""
    _roles, segments, _extras = raceresult._map_columns(_payload_rumilly())

    assert segments == [
        ("Nat.", 9), ("T1", 11), ("Vélo", 13), ("T2", 15), ("CAP", 17)
    ]
    indices_de_rang_de_split = {8, 10, 12, 14, 16}
    assert not indices_de_rang_de_split & {col for _label, col in segments}


def test_map_columns_range_les_champs_non_reconnus_en_extras():
    """Un champ inconnu n'est pas perdu : il partira dans `raw_data`."""
    _roles, _segments, extras = raceresult._map_columns(_payload_rumilly())

    assert extras["Arrivée.OVERALL.GapTop"] == 19
    # `DossardBis` n'y est pas : c'est une colonne d'affichage du dossard, que
    # `_role` écarte — le dossard vient de `DataFields.index("BIB")`.
    assert "DossardBis" not in extras


def test_map_columns_gere_un_fields_vide_ou_absent():
    """I2 : `Fields` vide (`[]`) ou `list` absent ne doit laisser passer que le
    rôle `bib`, jamais lever — sans reproduire en silence le symptôme de C1
    (une liste qui ne renseigne aucun rôle exploitable)."""
    assert raceresult._map_columns({"DataFields": ["BIB"]}) == ({"bib": 0}, [], {})
    assert raceresult._map_columns(
        {"DataFields": ["BIB"], "list": {"Fields": []}}
    ) == ({"bib": 0}, [], {})
    assert raceresult._map_columns({"DataFields": ["BIB"], "list": {}}) == (
        {"bib": 0}, [], {},
    )


# ── Vocabulaire réel des expressions (§6 du sondage) ────────────────────────

@pytest.mark.parametrize("expr,role", [
    # Enveloppe `if([STATUS]<>2;[X])`, omniprésente sur les épreuves récentes.
    # Retenir le terme le plus long tout court sélectionnait `[STATUS]<>2` et
    # faisait perdre TOUS les segments de Genève et Besançon.
    ("if([STATUS]<>2;[TIME])", "temps"),
    ("if([SEX]=\"f\";[SexeMF])", "sexe"),
    ("if([Relais]=1;ucase([NomRelais]);[AfficherNom])", "nom"),
    # Rangs nommés : doivent passer AVANT la règle du suffixe `.p`, sinon
    # `AUTORANK.p` est pris pour un rang de split et l'épreuve perd son
    # classement général.
    ("OuStatut([AUTORANK.p])", "rang"),
    ("OuStatut([ClassementGénéral.P])", "rang"),
    ("ClassementGeneralp", "rang"),
    # Vocabulaire relevé hors de l'épreuve d'origine.
    ("LFNAME", "nom"),
    ("DisplayNameAsterisk", "nom"),
    ("TempsOuStatut", "temps"),
    ("Format([TempsFinal.DECIMAL];\"hh:mm:ss\")", "temps"),
    ("Arrivée.CHIP", "temps"),
    ("CLUB", "club"),
    # Concaténation `X & iif(…)` : la valeur est portée par le premier terme.
    ("ucase([SEX]) & iif([SexeMF]>0;\" (\" & [RANK2p] & \")\";\"\")", "sexe"),
    ("[AGEGROUP1.NAMESHORT] & iif([AGEGROUP1.NAMESHORT]>0;\"x\";\"\")", "rang_categorie"),
    # `#[ClassementMF.p][SexeMF]` colle le rang de sexe au sexe.
    ("#[ClassementMF.p][SexeMF]", "sexe"),
    # Colonnes d'affichage du dossard : écartées, le dossard vient de `BIB`.
    ("\"#\"&[BIB]", "dossard_affiche"),
    ("DossardBis", "dossard_affiche"),
    ("DisplayBib", "dossard_affiche"),
    # Rangs de split : « 2. » n'est pas le temps de natation.
    ("[Natation.OVERALL.P]", "rang_de_split"),
    # Bruit d'affichage : aucun rôle, part en extras.
    ("Icone(\"photos\")", ""),
    ("GapTimeTop(1;2;\"-\";\"+HH:MM:ss\")", ""),
])
def test_role_du_vocabulaire_reel(expr, role):
    assert raceresult._role(raceresult._peel(expr)) == role


# ── C4 : vocabulaire de temps franco-centré (règle de forme) ───────────────
#
# La table d'égalités exactes de `_role` anticipait `Arrivée.GUN`/`Arrivée.CHIP`
# et `Finish` nu, mais pas les variantes anglaises suffixées `Finish.GUN` /
# `Finish.CHIP` : constaté sur l'épreuve 380823 (Bike & Run de Pontcharra),
# dont les 58 participants perdaient leur `total_time` faute de rôle reconnu
# pour `Finish.GUN`. Plutôt que trois entrées de plus (qui échoueraient en
# silence sur la prochaine variante non relevée), `_RE_TEMPS_SUFFIXE` généralise
# par la forme : préfixe fermé (`temps`/`arrivee`/`finish`) + suffixe fermé
# (`.gun`/`.chip`/`.text`). Les cas ci-dessous couvrent les deux sens du
# balancier qui a fait échouer C1 deux fois : la reconnaissance ET sa
# non-sur-généralisation — d'où le maintien de `Finisher.CHIP` parmi les cas
# négatifs.
#
# La racine `finishresult` ajoutée par C1 ne fait **pas** partie de ce préfixe :
# le suffixe y étant mutualisé, elle y aurait aussi rendu reconnus
# `finishresult.gun`/`.chip`, jamais observés et de priorité haute. Elle vit
# dans sa propre constante appariée à `.text` (`_RE_TEMPS_RESULTAT_TEXTE`), ce
# qui est précisément ce que vérifient les cas négatifs `FinishResult.GUN` /
# `FinishResult.CHIP` plus bas.

@pytest.mark.parametrize("expr,role", [
    # Positif : les trois préfixes de `_RE_TEMPS_SUFFIXE` croisés avec ses trois
    # suffixes — dont les variantes qui ne sont apparues sur aucune épreuve du
    # panel mais que la forme couvre. `.text` reçoit un rôle distinct
    # (`temps_texte`, pas `temps`) : cf.
    # `test_map_columns_le_texte_ne_declasse_pas_un_chip_qui_le_precede`
    # (Mineur 2 de la revue C4) pour la raison. La dernière entrée, elle, relève
    # de la constante appariée de C1 et non de ce croisement.
    ("Finish.GUN", "temps_pistolet"),
    ("Finish.CHIP", "temps"),
    ("Finish.TEXT", "temps_texte"),
    ("Temps.GUN", "temps_pistolet"),
    ("Temps.CHIP", "temps"),
    ("Temps.TEXT", "temps_texte"),
    ("Arrivée.GUN", "temps_pistolet"),
    ("Arrivée.CHIP", "temps"),
    ("Arrivée.TEXT", "temps_texte"),
    # `FinishResult` (C1) : racine distincte, **appariée à son seul suffixe**
    # `.text` (`_RE_TEMPS_RESULTAT_TEXTE`), donc au rôle le plus faible. Un
    # chip ou un gun publié par la même liste continue de primer.
    ("FinishResult.TEXT", "temps_texte"),
    # `Temps` nu (Important 1 de la revue C4) : la table d'égalités exactes
    # contenait `finish`/`arrivee` nus et l'anglais `time`, mais pas le
    # français `temps` — trou du même vocabulaire que celui que C4 ferme,
    # révélé par la revue.
    ("Temps", "temps"),
    ("TEMPS", "temps"),
])
def test_role_regle_de_forme_temps_gun_chip_text(expr, role):
    assert raceresult._role(raceresult._peel(expr)) == role


@pytest.mark.parametrize("expr", [
    # Mineur 3 de la revue C1 : la racine `finishresult` est appariée au seul
    # suffixe `.text`. Le suffixe de `_RE_TEMPS_SUFFIXE` étant mutualisé, une
    # quatrième entrée dans son préfixe aurait aussi reconnu ces deux formes —
    # et leur aurait donné une priorité **haute**, alors qu'aucune n'a jamais
    # été observée. Les rejeter rend la propriété de sûreté de C1 (« la racine
    # ne peut obtenir que le rôle le plus faible ») vraie par construction.
    "FinishResult.GUN",
    "FinishResult.CHIP",
    # Préfixe qui contient `finish`/`temps` sans lui être égal : la forme ne
    # doit reconnaître QUE les trois racines fermées, pas un préfixe large.
    "Finisher.CHIP",
    "TempsIntermediaire.CHIP",
    "TempsIntermediaire.GUN",
    # Idem pour `temps` nu (Important 1) : l'ajout à la table d'égalités
    # exactes est une comparaison stricte (`peeled in (...)`), pas un test de
    # sous-chaîne — `TempsIntermediaire` seul (sans suffixe gun/chip/text) ne
    # doit matcher ni la table ni la règle de forme.
    "TempsIntermediaire",
    # Suffixe hors du vocabulaire fermé : une colonne d'écart n'est pas un
    # temps d'arrivée.
    "Finish.GAP",
    "Arrivée.RANG",
    # Absence de suffixe qualifié : reste géré par la table d'égalités
    # exactes existante (`finish` nu), pas par la règle de forme.
    "Finish.OVERALL.GapTop",
])
def test_role_regle_de_forme_ne_sur_generalise_pas(expr):
    """Un jeton qui n'est pas un temps ne doit pas devenir `temps` par accident
    — le défaut symétrique explicitement mis en garde par le brief C4."""
    assert raceresult._role(raceresult._peel(expr)) == ""


def test_map_columns_reconnait_finish_gun_seul():
    """Reproduction du symptôme réel de 380823 : `Finish.GUN` est l'unique
    colonne de temps de l'épreuve (pas de chip publié). Avant C4, aucun rôle
    n'était reconnu et les 58 participants perdaient leur `total_time`.

    Ce test porte un **second** invariant, à ne pas retirer en le croyant
    accessoire (M15/M13) : `assert "Finish.OVERALL.GapTop" in extras` verrouille
    l'exclusion du point de `_RE_TOKEN_SIMPLE`. `Finish.OVERALL.GapTop` n'obtient
    aucun rôle (`_role` ne couvre que le suffixe `.p`) et sa valeur n'est jamais
    qualifiée par `_RE_DUREE`, qui n'intervient qu'en aval sur les segments
    retenus : c'est le point exclu du motif, et lui seul, qui garde cette
    expression qualifiée en extras plutôt que candidate au rôle de segment —
    où elle disparaîtrait de `raw_data` au lieu d'y être conservée."""
    payload = {
        "DataFields": ["BIB", "ID", "Finish.GUN", "Finish.OVERALL.GapTop"],
        "list": {"Fields": [
            {"Expression": "Finish.GUN", "Label": "Tps"},
            {"Expression": "Finish.OVERALL.GapTop", "Label": "Ecart"},
        ]},
    }

    roles, _segments, extras = raceresult._map_columns(payload)

    # `temps_pistolet` est promu `temps` en repli (aucun chip publié) — même
    # mécanisme de repli que pour `Arrivée.GUN`, la forme ne le change pas.
    assert roles["temps"] == 2
    assert "temps_pistolet" not in roles
    assert "Finish.OVERALL.GapTop" in extras

    r = raceresult._build_result(
        ["86", "1", "31:27", "--"], roles, _segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )
    assert r.total_time == "00:31:27"


# ── C1 : `FinishResult.TEXT`, le chrono des listes d'affichage ───────────────
#
# Symptôme réel de l'épreuve 406211 (World Triathlon Para Cup, Besançon) : ses
# 13 listes publiées sont des listes d'affichage LIVE dont la colonne de temps
# est une formule `switch(...)` au curseur d'affichage. `_peel` la réduit à
# `finishresult.text`, qu'aucun rôle ne reconnaissait : les 42 participants
# sortaient sans `total_time` alors que la valeur était bien dans la ligne,
# ce qui gelait la course en « en cours » pour `services/cache.is_fresh`
# (TTL 10 min au lieu de 30 j → re-scraping perpétuel).

def test_map_columns_reconnait_finishresult_text_de_406211():
    """Reproduction de la formule réelle de 406211, verbatim.

    C'est le cas que la règle de forme de C4 excluait délibérément, en laissant
    le préfixe fermé à `finish` : `finishresult` en est une racine distincte.
    """
    expr_temps = (
        "switch([{Selector.Splits}.NAME]=[Finish.NAME];[FinishResult.TEXT];"
        "[{Selector.Splits}.NAME]<>[Start.NAME];[{Selector.Splits}])"
    )
    payload = {
        "DataFields": ["BIB", "ID", "AfficherNom", expr_temps],
        "list": {"Fields": [
            {"Expression": "AfficherNom", "Label": "{EN:Name|FR:Name}"},
            {"Expression": expr_temps, "Label": "{EN:Time|DE:Zeit|FR:Time}"},
        ]},
    }

    assert raceresult._peel(expr_temps) == "finishresult.text", "prémisse"

    roles, segments, extras = raceresult._map_columns(payload)

    # Le rôle reste `temps_texte` : la promotion est ligne à ligne, sous
    # condition de durée (cf. le test négatif ci-dessous).
    assert roles["temps_texte"] == 3
    assert "temps" not in roles

    r = raceresult._build_result(
        ["222", "1", "Jules RIBSTEIN", "1:03:01"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="PTS5 M", status_label="",
    )
    assert r.total_time == "01:03:01"
    assert r.status == "finisher"


@pytest.mark.parametrize("cellule", ["DNF", "DSQ", "DNS", "Abandon", "--", ""])
def test_build_result_un_statut_texte_ne_devient_pas_un_total_time(cellule):
    """Important 1 de la revue C1 — le défaut symétrique du correctif.

    La racine promue par C1 est précisément celle que RaceResult destine au
    *texte affiché* : sur une ligne non terminée, `FinishResult.TEXT` rend un
    libellé de statut, pas une durée. Or `total_time` n'a aucun garde-fou de
    forme en aval — `normalize_time` renvoie son entrée telle quelle quand elle
    ne la reconnaît pas (`utils.py`, `return s  # return as-is if
    unrecognized`) — et la ligne serait ensuite marquée `finisher`.

    Le repli `.text` est donc qualifié par `_RE_DUREE`, comme les segments.
    """
    payload = {
        "DataFields": ["BIB", "ID", "FinishResult.TEXT"],
        "list": {"Fields": [
            {"Expression": "FinishResult.TEXT", "Label": "Time"},
        ]},
    }
    roles, segments, extras = raceresult._map_columns(payload)

    r = raceresult._build_result(
        ["222", "1", cellule], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )

    assert r.total_time == "", f"{cellule!r} ne doit pas devenir un chrono"
    assert r.status != "finisher", "une ligne sans durée n'est pas un finisher"


def test_build_result_une_colonne_horloge_traverse_sans_garde_de_duree():
    """L'autre sens : la qualification `_RE_DUREE` ne vaut que pour `.text`.

    Une colonne d'horloge (`temps`, ou le pistolet déjà promu) ne rend qu'une
    durée ou rien, et doit traverser **y compris** dans les formats que
    `_RE_DUREE` ne couvre pas mais que `normalize_time` sait lire. Étendre la
    garde à toutes les colonnes de temps ferait perdre ces formats-là.
    """
    payload = {
        "DataFields": ["BIB", "ID", "TIME"],
        "list": {"Fields": [{"Expression": "TIME", "Label": "Temps"}]},
    }
    roles, segments, extras = raceresult._map_columns(payload)
    assert roles["temps"] == 2, "prémisse : colonne d'horloge"

    r = raceresult._build_result(
        ["222", "1", "1h23'45"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )

    assert not raceresult._RE_DUREE.match("1h23'45"), "prémisse : _RE_DUREE la rejette"
    assert r.total_time == "01:23:45"


def test_map_columns_un_chip_prime_sur_finishresult_text():
    """L'autre sens du balancier : l'élargissement de C1 ne doit pas évincer un
    temps mieux qualifié. `FinishResult.TEXT` reçoit `temps_texte`, le rôle le
    plus faible, **même quand il précède le chip** dans `Fields` — c'est la
    raison d'être du rôle distinct plutôt que d'un `temps` direct."""
    payload = {
        "DataFields": ["BIB", "ID", "FinishResult.TEXT", "Finish.CHIP"],
        "list": {"Fields": [
            {"Expression": "FinishResult.TEXT", "Label": "Tps affiché"},
            {"Expression": "Finish.CHIP", "Label": "Tps officiel"},
        ]},
    }

    roles, _segments, _extras = raceresult._map_columns(payload)

    assert roles["temps"] == 3, "le chip officiel doit primer sur le texte"


def test_map_columns_prefere_le_chip_au_gun_sous_la_regle_de_forme():
    """Le même arbitrage chip > gun que l'ancienne table d'égalités exactes,
    mais exercé via `Finish.*` — variante jamais vue avec les deux temps sur
    le panel, mais que la règle de forme doit traiter identiquement à
    `Arrivée.*` (411749/410891, cf. mesures du rapport C4)."""
    payload = {
        "DataFields": ["BIB", "ID", "Finish.GUN", "Finish.CHIP"],
        "list": {"Fields": [
            {"Expression": "Finish.GUN", "Label": "Tps"},
            {"Expression": "Finish.CHIP", "Label": "Tps Réél"},
        ]},
    }

    roles, _segments, _extras = raceresult._map_columns(payload)

    assert roles["temps"] == 3, "le chip doit primer sur le gun"
    assert "temps_pistolet" not in roles


def test_map_columns_le_texte_ne_declasse_pas_un_chip_qui_le_precede():
    """Mineur 2 (revue C4) : `.text` reçoit le rôle distinct `temps_texte`,
    résolu en `temps` seulement en tout dernier repli (après le repli gun).

    Sans ce rôle distinct, `_map_columns` retient le PREMIER champ qui
    revendique `temps` (`role and role not in roles`) : une liste publiant
    `Finish.TEXT` avant `Finish.CHIP` dans `Fields` verrait le texte
    squatter `temps` et le chip, pourtant publié et mesuré, partir en extras.
    Branche spéculative — aucune épreuve sondée ne publie `.TEXT` sur
    `temps`/`arrivee`/`finish` — mais l'ordre de priorité doit rester sûr si
    elle s'active un jour."""
    payload = {
        "DataFields": ["BIB", "ID", "Finish.TEXT", "Finish.CHIP"],
        "list": {"Fields": [
            {"Expression": "Finish.TEXT", "Label": "Tps (texte)"},
            {"Expression": "Finish.CHIP", "Label": "Tps Réél"},
        ]},
    }

    roles, _segments, extras = raceresult._map_columns(payload)

    assert roles["temps"] == 3, "le chip doit primer sur le texte, même publié avant"
    # `temps_texte` survit désormais à `_map_columns` (C1 : sa promotion est
    # ligne à ligne, sous condition de durée), mais il ne prend pas la place du
    # chip — c'est ce que ce test garde.
    assert roles.get("temps_texte") != roles["temps"]
    # La colonne texte n'est pas renvoyée en extras : elle garde son rôle
    # `temps_texte`. Depuis C1 elle n'est plus *évincée* pour autant — elle
    # sert de repli ligne à ligne, y compris sur une ligne où le chip serait
    # vide (cf. le commentaire de `total_time` dans `_build_result`).
    assert "Finish.TEXT" not in extras


def test_map_columns_retient_le_texte_faute_de_chip_et_de_gun():
    """Repli de dernier recours : aucun temps mesuré publié, seul `.text`.

    Depuis C1, ce repli se résout dans `_build_result` et non dans
    `_map_columns` : la colonne `.text` peut rendre un statut plutôt qu'une
    durée, ce qui ne se décide qu'à la ligne. Le comportement observable —
    « faute de chip et de gun, le texte fait le `total_time` » — est inchangé.
    """
    payload = {
        "DataFields": ["BIB", "ID", "Finish.TEXT"],
        "list": {"Fields": [{"Expression": "Finish.TEXT", "Label": "Tps"}]},
    }

    roles, segments, extras = raceresult._map_columns(payload)

    assert roles["temps_texte"] == 2
    assert "temps" not in roles

    r = raceresult._build_result(
        ["12", "1", "2:08:00"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )
    assert r.total_time == "02:08:00"


def test_split_profondeur_ignore_les_separateurs_imbriques():
    """Une découpe naïve sur `;` coupe à l'intérieur du `switch(...)` interne et
    fait perdre la colonne : `if(a;switch(b;c);d)` a TROIS termes, pas quatre."""
    assert raceresult._split_profondeur(
        "[Relais]=1;switch([X]=1;[A];[B]);[AfficherNom]", ";"
    ) == ["[Relais]=1", "switch([X]=1;[A];[B])", "[AfficherNom]"]

    # Et sur l'expression complète, le rôle retenu reste le bon.
    expr = "if([Relais]=1;switch([X]=1;[A];[B]);[AfficherNom])"
    assert raceresult._role(raceresult._peel(expr)) == "nom"


def test_map_columns_prefere_le_temps_reel_au_temps_pistolet():
    """`Arrivée.GUN` (coup de pistolet) et `Arrivée.CHIP` (temps réel)
    coexistent sur les épreuves de trail — le temps officiel de l'athlète est
    le chip, alors que le gun apparaît en premier dans `Fields`."""
    payload = {
        "DataFields": ["BIB", "ID", "Arrivée.GUN", "Arrivée.CHIP"],
        "list": {"Fields": [
            {"Expression": "Arrivée.GUN", "Label": "Tps"},
            {"Expression": "Arrivée.CHIP", "Label": "Tps Réél"},
        ]},
    }

    roles, _segments, _extras = raceresult._map_columns(payload)

    assert roles["temps"] == 3, "le chip doit primer sur le gun"
    assert "temps_pistolet" not in roles


def test_map_columns_retient_le_pistolet_faute_de_chip():
    payload = {
        "DataFields": ["BIB", "ID", "Arrivée.GUN"],
        "list": {"Fields": [{"Expression": "Arrivée.GUN", "Label": "Tps"}]},
    }

    roles, _segments, _extras = raceresult._map_columns(payload)

    assert roles["temps"] == 2


def test_map_columns_detecte_un_segment_sans_crochets():
    """Certaines épreuves écrivent `Natation` là où d'autres écrivent
    `[Natation]` : exiger les crochets privait Roanne de tous ses splits."""
    payload = {
        "DataFields": ["BIB", "ID", "Natation", "Course"],
        "list": {"Fields": [
            {"Expression": "Natation", "Label": "Natation"},
            {"Expression": "Course", "Label": "Course"},
        ]},
    }

    _roles, segments, _extras = raceresult._map_columns(payload)

    assert segments == [("Natation", 2), ("Course", 3)]


def test_map_columns_exclut_customflag_de_406211():
    """I3 — `CustomFlag` (drapeau) n'est plus une candidate au rôle de segment.

    Sur l'event 406211, sa colonne est étiquetée `{FR:Nat.|EN:Team}`, soit
    « Nat. » une fois l'i18n retiré (I1) : **indiscernable de « Natation »**, à
    laquelle elle est ici juxtaposée. `peel('CustomFlag') == 'customflag'`
    passait `_RE_TOKEN_SIMPLE` ; le faux positif n'était neutralisé que parce que
    la valeur `[img:…]` est effacée par `_clean_cell`, donc falsy — par accident
    et non par conception.

    La colonne n'est pas perdue pour autant : elle retombe en extras → `raw_data`.
    """
    payload = {
        "DataFields": ["BIB", "ID", "CustomFlag", "Natation"],
        "list": {"Fields": [
            {"Expression": "CustomFlag", "Label": "{FR:Nat.|EN:Team}"},
            {"Expression": "Natation", "Label": "Natation"},
        ]},
    }

    _roles, segments, extras = raceresult._map_columns(payload)

    assert segments == [("Natation", 3)]
    assert extras == {"CustomFlag": 2}


def test_map_columns_exclut_customflag_meme_avec_une_valeur_textuelle():
    """I3, le cœur du correctif : l'exclusion ne dépend plus de la valeur.

    Une épreuve qui servirait son drapeau en texte (code pays) au lieu d'un
    `[img:…]` rouvrait le faux positif — la neutralisation par valeur vide ne
    tenait qu'à la forme des cellules observées.
    """
    payload = {
        "DataFields": ["BIB", "ID", "CustomFlag"],
        "list": {"Fields": [
            {"Expression": "CustomFlag", "Label": "Nat."},
        ]},
    }

    _roles, segments, _extras = raceresult._map_columns(payload)

    assert segments == []


@pytest.mark.parametrize("expr", [
    "CustomFlag",
    "LienPhotos",
    "Lienphotos",
    "[LienPhotos]",
    "NATION.IOCNAME",
    'Icone("photos")',
    'GapTimeTop(1;1;"--";"+H:mm:ss")',
])
def test_colonne_exclue_reconnait_les_colonnes_d_agrement(expr):
    """I3 — les cinq formes que le §6 du sondage demandait d'exclure, dans les
    graphies réellement relevées sur le panel (`LienPhotos`, `Lienphotos` et
    `[LienPhotos]` coexistent)."""
    assert raceresult._colonne_exclue(raceresult._peel(expr)) is True


@pytest.mark.parametrize("expr", [
    # Les vrais segments, sous leurs deux graphies.
    "Natation", "[Natation]", "Vélo", "[Vélo]", "Course", "Swim", "Bike", "Run",
    "Transition1", "[Transition_2]",
    # Une liste d'exclusion doit aussi **laisser passer** ce qui n'y figure pas :
    # ces colonnes restent candidates et continuent d'être arbitrées sur la
    # forme de leurs valeurs (`_RE_DUREE`), comme avant.
    "TIME19", "DistanceTotale", "Speed", "Year", "License",
    # Voisinages lexicaux : ni un préfixe ni un fragment ne doit suffire.
    "Flag", "Photos", "Icone", "GapTimeTopSplit", "Nation", "CustomFlagTime",
])
def test_colonne_exclue_laisse_passer_le_reste(expr):
    """I3, sens inverse : l'exclusion est ancrée sur l'expression **entière**
    (égalité exacte, ou préfixe suivi de la parenthèse ouvrante).

    `Icone` nu et `GapTimeTopSplit` ne sont pas les colonnes visées : sans cette
    précision, une liste d'exclusion mord sur des colonnes légitimes, ce qui est
    le symétrique — et le plus coûteux — du faux positif qu'elle corrige.
    """
    assert raceresult._colonne_exclue(raceresult._peel(expr)) is False


def test_build_result_ecarte_les_colonnes_qui_ne_sont_pas_des_durees():
    """Une colonne candidate au rôle de segment (`TIME19` étiquetée « Tours »,
    `DistanceTotale` étiquetée « Distance ») a la même forme d'expression qu'un
    split. Seule la valeur les sépare : `normalize_time` est permissif et
    laisse passer `107` ou `447.795`."""
    payload = {
        "DataFields": ["BIB", "ID", "Natation", "TIME19", "DistanceTotale"],
        "list": {"Fields": [
            {"Expression": "Natation", "Label": "Natation"},
            {"Expression": "TIME19", "Label": "Tours"},
            {"Expression": "DistanceTotale", "Label": "Distance"},
        ]},
    }
    roles, segments, extras = raceresult._map_columns(payload)

    r = raceresult._build_result(
        ["9046", "1", "13:16", "107", "447.795"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )

    assert r.segments == [("Natation", "00:13:16")]


def test_build_result_recupere_les_segments_malgre_la_concatenation_imbriquee():
    """C2 + C3 combinés, sur une capture réelle de l'épreuve 401699 (Half Iron
    du Lac d'Annecy, liste Individuel, athlète GOUAULT Pierre) : avant
    correctif, `_peel` s'arrêtait à `[Vélo] & " (" & [Vélo.OVERALL.P] & ")"`
    (composée, donc non reconnue comme segment) ET la valeur brute portait un
    rang collé (`"2:08:00 (1.)"`) que `_RE_DUREE` rejetait. Les deux causes
    devaient être corrigées pour que ce split réapparaisse."""
    payload = {
        "DataFields": [
            "BIB", "ID", "OuStatut([ClassementGénéral.p])", "AfficherNom",
            'if([STATUS]<>2;[Natation] & " (" & [Natation.OVERALL.P] & ")")',
            'if([STATUS]<>2;[Vélo] & " (" & [Vélo.OVERALL.P] & ")")',
            'if([STATUS]<>2;[Course] & " (" & [Course.OVERALL.P] & ")")',
            "OuStatut([TIME])",
        ],
        "list": {"Fields": [
            {"Expression": "OuStatut([ClassementGénéral.p])", "Label": "Rang"},
            {"Expression": "AfficherNom", "Label": "Nom"},
            {
                "Expression": 'if([STATUS]<>2;[Natation] & " (" & [Natation.OVERALL.P] & ")")',
                "Label": "Nat. + T1",
            },
            {
                "Expression": 'if([STATUS]<>2;[Vélo] & " (" & [Vélo.OVERALL.P] & ")")',
                "Label": "Vélo",
            },
            {
                "Expression": 'if([STATUS]<>2;[Course] & " (" & [Course.OVERALL.P] & ")")',
                "Label": "Course + T2",
            },
            {"Expression": "OuStatut([TIME])", "Label": "Temps"},
        ]},
    }
    roles, segments, extras = raceresult._map_columns(payload)
    ligne = ["452", "452", "1.", "GOUAULT Pierre", "28:51 (10.)", "2:08:00 (1.)", "41:30 (4.)", "3:18:21"]

    r = raceresult._build_result(
        ligne, roles, segments, extras,
        source_url="u", event_name="Half Iron du Lac d'Annecy", event_date=None,
        contest_label="Individuel", status_label="",
    )

    assert r.segments == [
        ("Nat. + T1", "00:28:51"),
        ("Vélo", "02:08:00"),
        ("Course + T2", "00:41:30"),
    ]


def test_build_result_decolle_le_rang_suffixe_dune_valeur_de_segment():
    """C3 isolé de C2 : sur la liste Relais de la même épreuve (401699),
    l'expression `[Vélo] & " (" & [Vélo.OVERALL.P] & ")"` pèle déjà
    correctement — `Vélo` est bien reconnu segment — mais seule la VALEUR
    porte le rang collé (`"2:08:00 (1.)"`), qui faisait rejeter la cellule par
    `_RE_DUREE`."""
    expr = '[Vélo] & " (" & [Vélo.OVERALL.P] & ")"'
    payload = {
        "DataFields": ["BIB", "ID", expr],
        "list": {"Fields": [{"Expression": expr, "Label": "Vélo"}]},
    }
    roles, segments, extras = raceresult._map_columns(payload)
    assert segments == [("Vélo", 2)]  # le peel n'était pas en cause ici

    r = raceresult._build_result(
        ["1", "1", "2:08:00 (1.)"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )

    assert r.segments == [("Vélo", "02:08:00")]


# ── Important 1 (revue du correctif C2+C3) : C2 élargit les rôles reconnus,
# une colonne temps/nom/club peut donc désormais provenir d'une concaténation
# composée `[X] & " (" & [X.OVERALL.P] & ")"` — exactement le motif qui polluait
# les segments avant C3. `_strip_rank_suffix` doit protéger ces trois cellules
# comme elle protège déjà les segments, sans quoi le rang collé migre en base
# (`total_time = "3:18:21 (5.)"`), symptôme C3 déplacé sur un chemin non
# corrigé. Motif repris verbatim de 401699 (§ Important 1 des constats de
# revue), avec le rôle substitué à `[TIME]` : aucune épreuve du panel ne
# l'expose telle quelle sur `temps`/`nom`/`club` (sondé en série sur les 12
# épreuves connues), mais le motif de concaténation lui-même est confirmé réel
# — seule sa combinaison avec ces rôles ne l'est pas encore.

def test_build_result_protege_le_temps_dune_colonne_composee():
    """Si `_peel` fait converger une colonne de temps composée vers le rôle
    `temps` (C2), sa valeur brute porte le même rang collé qu'un segment —
    `normalize_time` est permissif et laisserait passer `"3:18:21 (5.)"` tel
    quel si `_strip_rank_suffix` n'était pas appliqué avant."""
    expr = 'if([STATUS]<>2;[TIME] & " (" & [TIME.OVERALL.P] & ")")'
    payload = {
        "DataFields": ["BIB", "ID", expr],
        "list": {"Fields": [{"Expression": expr, "Label": "Temps"}]},
    }
    roles, segments, extras = raceresult._map_columns(payload)
    assert roles["temps"] == 2  # C2 : la concaténation imbriquée pèle en "temps"

    r = raceresult._build_result(
        ["1", "1", "3:18:21 (5.)"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )

    assert r.total_time == "03:18:21"


def test_build_result_protege_le_nom_et_le_club_dune_colonne_composee():
    """Même risque que pour `temps`, vérifié pour `nom` et `club` (constat
    Important 1) : une colonne de nom ou de club qui afficherait un rang de
    la même façon composée ne doit pas le laisser polluer la valeur."""
    expr_nom = 'if([Relais]=1;[NomRelais] & " (" & [NomRelais.OVERALL.P] & ")";[AfficherNom])'
    expr_club = '[CLUB] & " (" & [CLUB.OVERALL.P] & ")"'
    payload = {
        "DataFields": ["BIB", "ID", expr_nom, expr_club],
        "list": {"Fields": [
            {"Expression": expr_nom, "Label": "Nom"},
            {"Expression": expr_club, "Label": "Club"},
        ]},
    }
    roles, segments, extras = raceresult._map_columns(payload)
    assert roles["nom"] == 2
    assert roles["club"] == 3

    r = raceresult._build_result(
        ["1", "1", "DUPONT Jean (3.)", "TCN (12.)"], roles, segments, extras,
        source_url="u", event_name="E", event_date=None,
        contest_label="C", status_label="",
    )

    assert r.athlete_name == "DUPONT"
    assert r.athlete_firstname == "Jean"
    assert r.club == "TCN"


def test_resolve_event_id_exige_bien_les_deux_syntaxes():
    """Garde directe sur l'expression rationnelle : les deux façades réelles."""
    quote = 'new RRPublish(document.getElementById("d"), "392745", "results");'
    nu = 'new RRPublish(document.getElementById("d"), 411749, "results");'

    assert raceresult._RE_RRPUBLISH.search(quote).group(1) == "392745"
    assert raceresult._RE_RRPUBLISH.search(nu).group(1) == "411749"


# ── Groupes (contest / statut) ──────────────────────────────────────────────

@pytest.mark.parametrize("cle,attendu", [
    ("#1_Distance M", "Distance M"),
    ("#2_Abandons", "Abandons"),
    ("#1_", ""),
    ("Distance M", "Distance M"),
])
def test_strip_group_prefix(cle, attendu):
    assert raceresult._strip_group_prefix(cle) == attendu


def test_iter_groups_expose_contest_et_statut():
    groupes = raceresult._iter_groups(_payload_rumilly()["data"])

    assert [(c, s, len(lignes)) for c, s, lignes in groupes] == [
        ("Distance M", "", 2),
        ("Distance M", "Abandons", 2),
        ("Distance M", "Non Partants", 2),
    ]


def test_iter_groups_supporte_un_seul_niveau():
    """Certains payloads n'ont pas de sous-groupe de statut."""
    data = {"#1_Distance S": [["1", "2", "1.", "1"]]}

    assert raceresult._iter_groups(data) == [("Distance S", "", [["1", "2", "1.", "1"]])]


# ── Construction d'un ScrapedResult ─────────────────────────────────────────

def _construire(ligne, contest="Distance M", statut=""):
    payload = _payload_rumilly()
    roles, segments, extras = raceresult._map_columns(payload)
    return raceresult._build_result(
        ligne, roles, segments, extras,
        source_url="https://my3.raceresult.com/393893/results",
        event_name="Triathlon de Rumilly",
        event_date=date(2026, 6, 18),
        contest_label=contest,
        status_label=statut,
    )


def test_build_result_finisher():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][1]

    r = _construire(ligne)

    assert r.provider == "raceresult"
    assert r.bib_number == "79"
    assert r.athlete_name == "ROUX"
    assert r.athlete_firstname == "Alexis"
    assert r.gender == "M"
    assert r.club == "GRESIVAUDAN TRIATHLON"
    assert r.category == "S4M"
    assert r.rank_category == 1
    assert r.rank_overall == 2
    assert r.total_time == "02:01:56"
    assert r.status == "finisher"
    assert r.event_name == "Triathlon de Rumilly - Distance M"
    assert r.event_type == "triathlon-m"
    assert r.event_date == date(2026, 6, 18)


def test_build_result_nom_compose_en_prenom_nom():
    """`Jean DE LA TOUR` — le nom est le bloc majuscule entier (cf. Task 1).

    Ligne construite ici plutôt que lue dans la fixture : celle-ci est une
    capture réelle et ne contient aucun nom à particule. Fabriquer un tel
    athlète *dans* la fixture ferait mentir une capture — c'est précisément ce
    qui a laissé passer cinq défauts sur cette branche."""
    ligne = list(_payload_rumilly()["data"]["#1_Distance M"]["#1_"][1])
    ligne[4] = "Jean DE LA TOUR"

    r = _construire(ligne)

    assert (r.athlete_name, r.athlete_firstname) == ("DE LA TOUR", "Jean")


def test_build_result_segments_ordonnes_et_etiquetes():
    """Liste ordonnée, pas les 5 slots positionnels : le plafond de 5 est levé."""
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][1]

    r = _construire(ligne)

    assert r.segments == [
        ("Nat.", "00:20:04"),
        ("T1", "00:00:53"),
        ("Vélo", "01:05:49"),
        ("T2", "00:00:56"),
        ("CAP", "00:34:14"),
    ]


def test_build_result_extras_dans_raw_data():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][1]

    r = _construire(ligne)

    assert r.raw_data["Arrivée.OVERALL.GapTop"] == "+2:44"


def test_build_result_dnf_depuis_le_groupe():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#2_Abandons"][0]

    r = _construire(ligne, statut="Abandons")

    assert r.status == STATUS_DNF
    assert r.total_time == ""
    assert (r.rank_overall, r.rank_category, r.rank_gender) == (None, None, None)


def test_build_result_dns_depuis_le_groupe():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#3_Non Partants"][0]

    r = _construire(ligne, statut="Non Partants")

    assert r.status == STATUS_DNS
    assert r.total_time == ""


def test_build_result_statut_depuis_la_cellule_de_rang():
    """Sans groupe de statut, la cellule de rang vaut littéralement « DNF »."""
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#2_Abandons"][0]

    r = _construire(ligne, statut="")

    assert r.status == STATUS_DNF


def test_build_result_statut_du_groupe_sans_cellule():
    """Le groupe suffit : une cellule de rang vide ne dégrade pas le statut.

    Sans ce cas, `test_build_result_dnf_depuis_le_groupe` serait un faux vert —
    il passerait par le repli sur la cellule sans jamais exercer le groupe.
    """
    ligne = list(_payload_rumilly()["data"]["#1_Distance M"]["#2_Abandons"][0])
    ligne[2] = ""  # colonne de rang vidée

    assert _construire(ligne, statut="Abandons").status == STATUS_DNF
    assert _construire(ligne, statut="Non Partants").status == STATUS_DNS


def test_build_result_purge_temps_et_rangs_dun_non_finisher():
    """M15 : la purge finale, sur une ligne qui porte **vraiment** temps et rangs.

    Les lignes « Abandons » de la capture Rumilly ont déjà une cellule de temps
    vide : les tests qui s'en servent passeraient à l'identique sans la purge —
    ils constatent une absence, ils n'exercent pas le nettoyage. L'invariant
    n'était couvert que par `test_scrape_event_all_status_jamais_incoherent`
    (`tests/test_integration_scrapers.py`), marqué `integration`, donc jamais
    joué par la CI (`-m "not integration"`).

    Le cas réel qu'il faut tenir : une liste de classement annonce un chrono et
    des rangs pour un dossard qu'une autre liste range sous « Abandons » — le
    payload est contradictoire, et c'est le statut qui fait foi. Sans la purge,
    la course partirait en base avec un DNF chronométré et classé, et
    `services/cache.is_fresh` la croirait terminée.

    Deux sens : un finisher, lui, **conserve** temps et rangs.
    """
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][1]

    # Double rôle, à ne pas retirer comme un simple échafaudage : ce bloc est la
    # prémisse du cas polluant (la ligne est bien renseignée, la purge a donc de
    # quoi mordre — sans quoi les assertions du bas seraient vertes par accident
    # d'absence, exactement le travers des tests DNF existants), ET le **sens
    # légitime** de la garde : hors statut non-finisher, temps et rangs doivent
    # survivre intacts. Une purge inconditionnelle passerait le bas de ce test.
    finisher = _construire(ligne)
    assert finisher.total_time == "02:01:56"
    assert (finisher.rank_overall, finisher.rank_category, finisher.rank_gender) == (
        2, 1, None,
    )

    abandon = _construire(ligne, statut="Abandons")

    assert abandon.status == STATUS_DNF
    assert abandon.total_time == ""
    assert (abandon.rank_overall, abandon.rank_category, abandon.rank_gender) == (
        None, None, None,
    )


def test_build_result_le_groupe_prime_sur_la_cellule_en_cas_de_divergence():
    """M19 : précédence groupe > cellule, sur le seul cas qui les distingue.

    Tant que groupe et cellule s'accordent (tout le corpus de fixtures), les
    deux ordres de précédence rendent le même statut : la ligne de production
    est indiscernable de son inverse. Ils ne divergent qu'ici — un groupe
    « Non Partants » dont une ligne porte encore une cellule `OuStatut`
    contradictoire, résidu d'un statut antérieur au reclassement du dossard.

    Le groupe fait autorité parce qu'il est le classement **courant** de
    l'organisateur : il qualifie toute la tranche, là où la cellule n'est qu'un
    repli pour les payloads sans sous-groupe de statut.

    Deux sens : sans groupe reconnu, la cellule reprend la main.
    """
    ligne = list(_payload_rumilly()["data"]["#1_Distance M"]["#3_Non Partants"][0])
    ligne[2] = "DNF"  # cellule de rang contradictoire avec son groupe

    assert _construire(ligne, statut="Non Partants").status == STATUS_DNS
    assert _construire(ligne, statut="").status == STATUS_DNF


def _payload_401699_relais():
    """Liste relais de l'event 401699 (Half Iron du Lac d'Annecy), forme réelle.

    Capturée telle quelle : c'est la seule épreuve du panel dont les valeurs de
    catégorie portent l'enrobage i18n (`CatégorieRelais` rend
    `{EN:Men|FR:Masculin}`), d'où son rôle de témoin pour I1.
    """
    return {
        "DataFields": [
            "BIB", "ID", "OuStatut([ClassementGénéral.p])", "NomRelais",
            "CatégorieRelais", '" (" & [ClassementRelais.p] & ")"',
            "AfficherNoms",
            '[Natation] & " (" & [Natation.OVERALL.P] & ")"',
            "OuStatut([TIME])",
        ],
        "list": {"Fields": [
            {"Expression": "OuStatut([ClassementGénéral.p])", "Label": "Rang"},
            {"Expression": "BIB", "Label": "Dos."},
            {"Expression": "NomRelais", "Label": "Nom"},
            {"Expression": "CatégorieRelais", "Label": "Cat."},
            {"Expression": '" (" & [ClassementRelais.p] & ")"', "Label": ""},
            {"Expression": "AfficherNoms", "Label": "Relayeurs"},
            {"Expression": '[Natation] & " (" & [Natation.OVERALL.P] & ")"',
             "Label": "Nat. + T1"},
            {"Expression": "OuStatut([TIME])", "Label": "Temps"},
        ]},
        "data": {"#1_Relais": [[
            "614", "565", "1.", "COLLER AU PARQUET", "{EN:Men|FR:Masculin}",
            " (1.)", "VIDAL Florian, L'HER Antonin, DUSSUCHAL Pierrick",
            "33:18 (10.)", "3:35:02",
        ]]},
    }


def test_build_result_categorie_i18n_de_401699_entre_lisible():
    """I1, bout en bout sur la forme réelle : la catégorie relais de 401699
    n'entre plus en base sous son enrobage i18n.

    Verrou d'anti-régression : `_label_i18n` n'était appliqué qu'aux libellés de
    colonne, si bien que `category` valait `'{EN:Men|FR:Masculin}'`.
    """
    payload = _payload_401699_relais()
    roles, segments, extras = raceresult._map_columns(payload)
    ligne = payload["data"]["#1_Relais"][0]

    r = raceresult._build_result(
        ligne, roles, segments, extras,
        source_url="https://my.raceresult.com/401699/results",
        event_name="Half Iron du Lac d'Annecy",
        event_date=date(2026, 6, 21),
        contest_label="Relais",
        status_label="",
    )

    assert r.category == "Masculin"
    # Le reste de la ligne est inchangé : le correctif ne touche qu'à l'enrobage.
    assert r.athlete_name == "COLLER AU PARQUET"
    assert r.total_time == "03:35:02"
    assert r.segments == [("Nat. + T1", "00:33:18")]


def test_build_result_marque_le_relais():
    ligne = _payload_rumilly()["data"]["#1_Distance M"]["#1_"][0]

    r = _construire(ligne, contest="Relais M")

    assert r.is_relay is True


# ── Richesse (arbitrage des doublons) ───────────────────────────────────────

def test_richness_ignore_les_extras_vides():
    """I1 : `raw_data` n'est pas filtré des cellules vides — une ligne quasi
    vide (dossard seul, deux extras vides) ne doit pas peser autant qu'une
    ligne réellement renseignée."""
    pauvre = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="1",
        raw_data={"Extra1": "", "Extra2": ""},
    )
    riche = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="1",
        club="GRESIVAUDAN TRIATHLON",
    )

    assert raceresult._richness(pauvre) == 0
    assert raceresult._richness(riche) == 1
    assert raceresult._richness(riche) > raceresult._richness(pauvre)


def test_prefer_un_temps_reel_prime_sur_la_seule_richesse():
    """C1 : une ligne plus riche en colonnes mais sans temps réel — cas d'une
    liste d'affichage LIVE dont les colonnes techniques (drapeau, écart au
    leader…) partent en extras — ne doit pas écraser une ligne moins riche
    mais porteuse d'un vrai temps d'arrivée. Reproduction directe du contest
    « Distance Jeunes » (event 393893) : `03 - Affichages|LIVE EXTRA sans
    predictif` (aucun temps décodé, seul le dossard brut en extra) contre
    `04 - Classements|Classement général Jeunes` (rang 1, temps 00:09:08)."""
    pauvre_avec_temps = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="24",
        athlete_name="MARCHAND", total_time="00:09:08", rank_overall=1,
    )
    riche_sans_temps = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="24",
        athlete_name="MARCHAND",
        raw_data={"{DE:Startnr|EN:Bib|FR:Dos.}": "24", "Extra": "x"},
    )

    assert raceresult._prefer(riche_sans_temps, pauvre_avec_temps) is False
    assert raceresult._prefer(pauvre_avec_temps, riche_sans_temps) is True


def test_prefer_un_non_finisher_arrivant_en_second_ecrase_une_ligne_muette():
    """M3 : les deux gardes non-finisher de `_prefer` sont **asymétriques**.

    La seconde (`ancien.status …`) protège un DNF déjà retenu ; seule la
    première protège un DNF qui arrive **après** une ligne muette. Sans elle,
    l'ordre des listes déciderait du statut : la ligne muette, plus riche en
    colonnes d'affichage, l'emporterait sur la seule liste qui sait que le
    dossard a abandonné — et le participant sortirait sans statut.

    Le test tient les deux sens de la garde, conjonction comprise :
      - face à une ligne muette **sans temps**, le DNF second doit écraser ;
      - face à une ligne portant un **vrai chrono**, il ne doit pas — un temps
        d'arrivée réel reste un signal plus fort qu'un statut annoncé (cas de
        la liste « Non Partants » figée à la veille).
    """
    dnf_muet = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="9",
        athlete_name="ROUSSELON", status=STATUS_DNF,
    )
    riche_sans_temps = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="9",
        athlete_name="ROUSSELON", club="AIX SAVOIE TRIATHLON", gender="M",
        raw_data={"Drapeau": "fr", "Écart": "+2:44"},
    )
    avec_temps = ScrapedResult(
        source_url="x", provider="raceresult", bib_number="9",
        athlete_name="ROUSSELON", total_time="02:01:56", rank_overall=2,
    )

    # Sens 1 : le DNF arrive en second sur une ligne muette, pourtant plus riche.
    assert raceresult._richness(riche_sans_temps) > raceresult._richness(dnf_muet)
    assert raceresult._prefer(dnf_muet, riche_sans_temps) is True

    # Sens 2 : le même DNF n'écrase pas un chrono réel (non-régression 0a1536d).
    assert raceresult._prefer(dnf_muet, avec_temps) is False


# ── Pipeline complet : listes explicites, fusion, erreurs ───────────────────

def test_fetch_list_renvoie_none_sur_404():
    """Une liste annoncée mais non servie n'interrompt pas le balayage."""
    client = _FauxClient({"/results/list": (404, "")})

    assert raceresult._fetch_list("393893", "k", "L", "1", client) is None


def test_fetch_list_renvoie_none_sur_payload_sans_data():
    client = _FauxClient({"/results/list": (200, '{"DataFields": [], "data": {}}')})

    assert raceresult._fetch_list("393893", "k", "L", "1", client) is None


def test_fetch_list_interroge_la_route_canonique():
    """C-A : même garde que pour la config, côté liste."""
    client = _FauxClient({"/results/list": (200, '{"DataFields": [], "data": {}}')})

    raceresult._fetch_list("393893", "cle", "04|Général", "4", client)

    appel = client.appels[0]
    assert "/393893/results/list" in appel
    assert "RRPublish/data" not in appel
    assert "contest=4" in appel
    assert "key=cle" in appel


def test_fetch_list_propage_une_erreur_serveur():
    """I4, tranché : un 5xx ne doit PAS être dégradé en liste vide. Un import
    partiel dont toutes les lignes portent un temps fait basculer la Course en
    « terminée » pour `cache.is_fresh` → cache gelé 30 jours sur une perte
    évitable, alors qu'un échec dur remonte en `BatchFailure` et sera re-tenté."""
    client = _FauxClient({"/results/list": (503, "")})

    with pytest.raises(httpx.HTTPStatusError):
        raceresult._fetch_list("393893", "k", "L", "1", client)


# Un payload minimal : 3 colonnes (BIB, ID, nom, temps) et un arbre `data`.
def _payload(lignes_par_groupe: dict, *, avec_temps: bool = True) -> dict:
    champs = [
        {"Expression": "AfficherNom", "Label": "Nom"},
        {"Expression": "ucase([CLUB])", "Label": "Club"},
    ]
    data_fields = ["BIB", "ID", "AfficherNom", "ucase([CLUB])"]
    if avec_temps:
        champs.append({"Expression": "TIME", "Label": "Temps"})
        data_fields.append("TIME")
    return {
        "DataFields": data_fields,
        "list": {"Fields": champs},
        "data": lignes_par_groupe,
    }


def _monte_pipeline(monkeypatch, specs, payloads):
    """Câble `scrape_event_all` sur des payloads en mémoire.

    `payloads` mappe (listname, contest) → payload ou None. Les appels sont
    enregistrés pour vérifier qu'aucun balayage à l'aveugle ne subsiste.
    """
    appels: list[tuple[str, str]] = []
    config = {
        "key": "k",
        "eventname": "Épreuve",
        "contests": {"1": "Distance S", "2": "Distance M"},
        "TabConfig": {"Lists": [
            {"Name": n, "Contest": c, "Mode": ""} for n, c in specs
        ]},
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


def test_scrape_event_all_interroge_exactement_les_listes_annoncees(monkeypatch):
    """Le contest étant explicite dans `TabConfig.Lists`, il n'y a plus rien à
    découvrir : une requête par couple annoncé, ni plus ni moins. L'ancienne
    version balayait `contest=0` puis chaque contest déclaré, soit 15 requêtes
    dont 11 en 404 sur Rumilly."""
    specs = [("Classement", "1"), ("Classement", "2")]
    payloads = {
        ("Classement", "1"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]}}),
        ("Classement", "2"): _payload({"#1_Distance M": {"#1_": [["8", "2", "Luc MARTIN", "TCN", "02:00:00"]]}}),
    }
    appels = _monte_pipeline(monkeypatch, specs, payloads)

    res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert appels == [("Classement", "1"), ("Classement", "2")]
    assert len(res) == 2


def test_scrape_event_all_qualifie_par_contest(monkeypatch):
    """Issue #21 : chaque contest devient une Course distincte, sans quoi deux
    dossards identiques de contests différents entrent en collision."""
    specs = [("Classement", "1"), ("Classement", "2")]
    payloads = {
        ("Classement", "1"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]}}),
        ("Classement", "2"): _payload({"#1_Distance M": {"#1_": [["7", "2", "Luc MARTIN", "TCN", "02:00:00"]]}}),
    }
    _monte_pipeline(monkeypatch, specs, payloads)

    res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert len(res) == 2, "même dossard, deux contests : aucune collision"
    assert {r.event_name for r in res} == {
        "Épreuve - Distance S", "Épreuve - Distance M"
    }


def test_scrape_event_all_fusionne_deux_listes_du_meme_contest(monkeypatch):
    """Plusieurs listes couvrent couramment un même contest (6 sur le contest 1
    de l'event 392745). La plus riche l'emporte, sans dupliquer le participant."""
    specs = [("Maigre", "1"), ("Riche", "1")]
    payloads = {
        ("Maigre", "1"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "", "01:00:00"]]}}),
        ("Riche", "1"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]}}),
    }
    _monte_pipeline(monkeypatch, specs, payloads)

    res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert len(res) == 1
    assert res[0].club == "TCN", "la ligne renseignée doit primer"


def test_scrape_event_all_un_groupe_par_sexe_n_est_pas_un_statut(monkeypatch):
    """C-E / §7 : sur l'event 406212 le niveau 2 porte `#1_Masculin` /
    `#1_Féminin`, un groupement par **sexe**. Interpréter tout libellé de groupe
    comme un statut y marquerait abandonnés tous les finishers."""
    specs = [("Classement", "1")]
    payloads = {("Classement", "1"): _payload({"#1_Distance S": {
        "#1_Masculin": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]],
        "#2_Féminin": [["8", "2", "Marie CURIE", "TCN", "01:10:00"]],
        "#3_Abandons": [["9", "3", "Luc MARTIN", "TCN", ""]],
    }})}
    _monte_pipeline(monkeypatch, specs, payloads)

    res = {r.bib_number: r for r in raceresult.scrape_event_all(
        "https://my.raceresult.com/1/results")}

    assert res["7"].status == "finisher"
    assert res["8"].status == "finisher"
    assert res["9"].status == STATUS_DNF, "un libellé RECONNU reste un statut"


def test_iter_groups_un_libelle_inconnu_n_efface_pas_le_statut_herite():
    """Le libellé d'un sous-groupe n'est retenu comme statut que s'il est
    reconnu. Sans cette garde, un groupement neutre imbriqué SOUS un groupe de
    statut effacerait ce dernier.

    Propriété de robustesse : l'imbrication statut → sexe n'a pas été observée
    sur le panel (qui ne dépasse pas deux niveaux), mais l'ordre inverse
    (sexe → statut) l'a été sur l'event 406212, et rien dans l'API ne garantit
    que RaceResult n'émette pas l'un après l'autre. La garde coûte une ligne ;
    ce test la rend vérifiable au lieu de la laisser en pari."""
    data = {"#1_Distance M": {"#2_Abandons": {"#1_Masculin": [["9", "3", "x"]]}}}

    assert raceresult._iter_groups(data) == [
        ("Distance M", "Abandons", [["9", "3", "x"]])
    ]


def test_scrape_event_all_supporte_les_profondeurs_variables(monkeypatch):
    """§7 : `data` est tantôt un tableau plat, tantôt à un niveau, tantôt à
    deux — parfois au sein d'une même épreuve. La descente est récursive."""
    specs = [("Plat", "1"), ("UnNiveau", "2")]
    payloads = {
        ("Plat", "1"): _payload([["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]),
        ("UnNiveau", "2"): _payload(
            {"#1_Distance M": [["8", "2", "Luc MARTIN", "TCN", "02:00:00"]]}
        ),
    }
    _monte_pipeline(monkeypatch, specs, payloads)

    res = {r.bib_number: r for r in raceresult.scrape_event_all(
        "https://my.raceresult.com/1/results")}

    assert set(res) == {"7", "8"}
    # Sans libellé de groupe, le repli est la table `contests`, plus parlante
    # que le nom de liste (lequel ne sert que si `contests` ne sait rien, cas
    # des listes en `Contest="0"`).
    assert res["7"].event_name == "Épreuve - Distance S"
    assert res["8"].event_name == "Épreuve - Distance M"


def test_scrape_event_all_ignore_une_liste_absente(monkeypatch):
    """Un 404 sur une liste annoncée n'emporte pas l'épreuve."""
    specs = [("Morte", "1"), ("Vivante", "2")]
    payloads = {
        ("Morte", "1"): None,
        ("Vivante", "2"): _payload({"#1_Distance M": {"#1_": [["8", "2", "Luc MARTIN", "TCN", "02:00:00"]]}}),
    }
    _monte_pipeline(monkeypatch, specs, payloads)

    res = raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert len(res) == 1


def test_scrape_event_all_sans_liste_exploitable_leve(monkeypatch):
    specs = [("Morte", "1")]
    _monte_pipeline(monkeypatch, specs, {("Morte", "1"): None})

    with pytest.raises(ValueError, match="aucune liste exploitable"):
        raceresult.scrape_event_all("https://my.raceresult.com/1/results")


def test_scrape_event_all_ouvre_le_client_avec_follow_redirects(monkeypatch):
    vus: dict = {}
    vrai_client = httpx.Client

    def espion(*args, **kwargs):
        vus.update(kwargs)
        return vrai_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", espion)
    specs = [("Classement", "1")]
    _monte_pipeline(monkeypatch, specs, {
        ("Classement", "1"): _payload({"#1_Distance S": {"#1_": [["7", "1", "Jean DUPONT", "TCN", "01:00:00"]]}}),
    })

    raceresult.scrape_event_all("https://my.raceresult.com/1/results")

    assert vus.get("follow_redirects") is True

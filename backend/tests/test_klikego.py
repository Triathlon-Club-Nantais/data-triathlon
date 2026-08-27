"""
Tests unitaires pour scrapers/klikego.py.

Chaque test correspond à un cas réel rencontré lors du développement :
- Redon Sprint       : pas de splits intermédiaires
- Domino             : labels "Chg Nat." / "Chg Vé." pour T1/T2
- Lacanau            : temps cumulés détectés automatiquement
- S1H/S2F            : catégories numériques parsées depuis la méta-ligne
- Frenchman XXL / Lac au Duc : détection du type d'épreuve depuis le heat
- Duathlon           : "CAP 1"/"CAP 2" → swim_time/run_time, heat "duathlon-s-individuel"
- Swimrun            : type détecté depuis le slug URL (heat = "format-l-en-binome")
- _parse_search_row  : extraction des lignes de résultat paginées (bulk import)
- scrape_event_all   : import exhaustif via data block (finishers + DNF/DNS/DSQ)
"""
import base64
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

import app.scrapers.klikego as klikego
import app.scrapers.klikego_platform as plat
from app.scrapers.base import ScrapedResult
from app.scrapers.classify import classify_event_type
from tests.conftest import load_klikego_fixture

_parse_detail = klikego._parse_detail
_parse_search_row = klikego._parse_search_row
decode_data_block = plat.decode_data_block
parse_data_row = plat.parse_data_row

FIXTURES = Path(__file__).parent / "fixtures"

# ── Helper ───────────────────────────────────────────────────────────────────

def make_detail_html(
    meta: str = "M - Dossard N°123 - V1H - CLUB TEST",
    total_time: str = "01:30:00",
    ranks: list[tuple[str, str]] | None = None,
    splits: list[tuple[str, str]] | None = None,
) -> str:
    """
    Génère du HTML minimal que _parse_detail() sait lire.

    Structure attendue par le scraper :
      <p class="text-sm">   → méta-ligne (genre / dossard / catégorie / club)
      paires de <div> siblings → "Temps Officiel" + valeur, labels classements
      <tr class="result-row" data-dossard="…"> → lignes de splits
    """
    rank_html = ""
    if ranks:
        for label, val in ranks:
            rank_html += f"<div>{label}</div><div>{val}</div>\n"

    splits_html = ""
    if splits:
        for stage, t in splits:
            splits_html += (
                f'<tr class="result-row" data-dossard="123">'
                f"<td>{stage}</td><td>{t}</td>"
                f"</tr>\n"
            )

    return f"""
    <html><body>
      <p class="text-sm">{meta}</p>
      <div id="times">
        <div>Temps Officiel</div>
        <div>{total_time}</div>
        {rank_html}
      </div>
      <table><tbody>
        {splits_html}
      </tbody></table>
    </body></html>
    """


def fresh_result() -> tuple[ScrapedResult, dict]:
    return ScrapedResult(source_url="http://test", provider="klikego"), {}


# ── _detect_event_type ───────────────────────────────────────────────────────

@pytest.mark.parametrize("heat,slug,expected", [
    # --- Triathlon (non-régression) ---
    ("triathlon-s", "", "triathlon-s"),
    ("triathlon-s-individuel", "", "triathlon-s"),
    # Lac au Duc : heat auto-détecté comme "format-s-en-individuel"
    ("format-s-en-individuel", "", "triathlon-s"),
    ("triathlon-m", "", "triathlon-m"),
    # Domino : "triathlon-m---individuel"
    ("triathlon-m---individuel", "", "triathlon-m"),
    # Mesquer (#153) : le slug d'événement mentionne « swimrun », le heat nomme déjà le sport → contexte ignoré
    ("triathlon-s-indiv", "triathlon-et-swimrun-mesquer-quimiac-2026", "triathlon-s"),
    ("triathlon-l", "", "triathlon-l"),
    ("triathlon-xl", "", "triathlon-xl"),
    # Frenchman XXL
    ("medoc-atlantique-frenchman-xxl", "", "triathlon-xl"),
    # --- Duathlon : sous-formats XS/S/M/L + vérification pas de régression -s triathlon ---
    ("duathlon-classique", "", "duathlon"),                                    # pas de format → générique
    ("duathlon-s-individuel", "", "duathlon-s"),                               # était "triathlon-s" avant fix
    ("duathlon-liffre-cormier-open--xs-court", "", "duathlon-xs"),             # XS
    ("duathlon-liffre-cormier-open--sprint-court", "", "duathlon-s"),          # sprint → S
    ("duathlon-m-individuel", "", "duathlon-m"),
    ("duathlon-l-individuel", "", "duathlon-l"),
    ("duathlon-liffre-cormier-clm-par-equipe", "", "duathlon"),                # relais → générique
    # --- Swimrun : sous-formats S/M/L depuis heat "format-x-…" ---
    ("swimrun-classique", "", "swimrun"),                                       # heat contient "swimrun"
    ("format-s---en-binome", "re-swimrun-2025", "swimrun-s"),
    ("format-m---en-solo", "swimrun-cote-beaute-2025", "swimrun-m"),
    ("format-l---championnat-de-france---en-binome", "re-swimrun-2025", "swimrun-l"),
    # --- Aquathlon / aquarun / bike-run : détectés avant les distances triathlon ---
    ("aquathlon-s-champnat", "aquathlon-des-2-amants-2025", "aquathlon"),      # "-s-" ne doit pas → triathlon-s
    ("aquathlon-individuel", "", "aquathlon"),
    ("aquarun-individuel", "aquarun-lacanau-2025", "aquarun"),
    ("bike-run-individuel", "bike-run-halloween-2025", "bike-run"),
    ("bikerun-sprint", "", "bike-run"),
    # Mimizan jeunes : heat "triathlon-xs-jeunes" → triathlon-xs (extra-short)
    ("triathlon-xs-jeunes", "", "triathlon-xs"),
    # heat vide → valeur brute retournée
    ("", "", "triathlon"),
])
def test_event_type_detection(heat, slug, expected):
    assert classify_event_type(heat, contexte=slug) == expected


# ── Redon Sprint : pas de splits, juste le temps total ───────────────────────

def test_parse_detail_no_splits():
    """Cas Redon Sprint — la page détail n'expose aucun split intermédiaire."""
    html = make_detail_html(total_time="00:58:42", splits=[])
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.total_time == "00:58:42"
    assert result.swim_time == ""
    assert result.t1_time == ""
    assert result.bike_time == ""
    assert result.t2_time == ""
    assert result.run_time == ""
    assert raw.get("cumulative") is False


# ── Domino : "Chg Nat." → t1, "Chg Vé." → t2 ─────────────────────────────────

def test_parse_detail_chg_nat_velo():
    """Cas Domino Val-de-Loire — T1/T2 labellisés "Chg Nat." / "Chg Vé."."""
    splits = [
        ("Natation", "00:18:00"),
        ("Chg Nat.", "00:01:30"),
        ("Vélo", "01:05:00"),
        ("Chg Vé.", "00:01:00"),
        ("Course à pied", "00:42:00"),
    ]
    html = make_detail_html(total_time="02:07:30", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.swim_time == "00:18:00"
    assert result.t1_time == "00:01:30"
    assert result.bike_time == "01:05:00"
    assert result.t2_time == "00:01:00"
    assert result.run_time == "00:42:00"
    assert raw["cumulative"] is False


# ── Lacanau : temps cumulés détectés et convertis en déltas ──────────────────

def test_parse_detail_cumulative_lacanau():
    """
    Cas Lacanau — la page retourne des temps cumulés (chaque split = temps
    depuis le départ). Le scraper doit les détecter automatiquement et
    calculer les durées par segment.

    Données cumulatives :
      Natation  → 00:15:00  (= 900 s)
      T1        → 00:17:30  (= 1050 s)
      Vélo      → 01:17:30  (= 4650 s)
      T2        → 01:20:00  (= 4800 s)
    Total       → 02:05:00  (= 7500 s)  → run déduit = 00:45:00
    """
    splits = [
        ("Natation", "00:15:00"),
        ("T1", "00:17:30"),
        ("Vélo", "01:17:30"),
        ("T2", "01:20:00"),
    ]
    html = make_detail_html(total_time="02:05:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert raw["cumulative"] is True
    assert result.swim_time == "00:15:00"   # 900 - 0
    assert result.t1_time  == "00:02:30"   # 1050 - 900
    assert result.bike_time == "01:00:00"  # 4650 - 1050
    assert result.t2_time  == "00:02:30"   # 4800 - 4650
    assert result.run_time == "00:45:00"   # 7500 - 4800 (dérivé du total)


def test_parse_detail_not_cumulative():
    """Temps par segment (non cumulatifs) — doivent être conservés tels quels."""
    splits = [
        ("Natation", "00:15:00"),   # 900 s
        ("T1", "00:02:30"),          # 150 s  < 900 → pas cumulatif
        ("Vélo", "01:00:00"),
        ("T2", "00:02:30"),
        ("Course à pied", "00:40:00"),
    ]
    html = make_detail_html(total_time="02:00:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert raw["cumulative"] is False
    assert result.swim_time == "00:15:00"
    assert result.t1_time   == "00:02:30"
    assert result.bike_time == "01:00:00"
    assert result.t2_time   == "00:02:30"
    assert result.run_time  == "00:40:00"


def test_parse_detail_km_checkpoint_does_not_shadow_section_summary():
    """
    Course 295 (#678) : un pointage kilométrique intermédiaire ("Vélo km 85")
    apparaît AVANT la ligne récapitulative "Vélo" dans le tableau détail
    (résultats en cours de finalisation, la ligne récap n'est pas encore
    postée). Le split_map d'origine matche les deux lignes par sous-chaîne
    ("vélo" ⊂ "vélo km 85"), et en mode non cumulatif la règle "premier
    arrivé, premier servi" de _set() figeait alors le temps partiel du
    pointage comme bike_time — la vraie ligne récapitulative n'écrivait plus
    que dans raw["split_vélo"], silencieusement. Idem côté course à pied avec
    "CAP km 14" / "Cap".
    """
    splits = [
        ("Natation", "00:15:00"),
        ("T1", "00:02:30"),
        ("Vélo km 85", "00:58:00"),   # pointage intermédiaire — PAS la vraie section
        ("Vélo", "01:00:00"),          # ligne récapitulative — doit gagner
        ("T2", "00:02:30"),
        ("CAP km 14", "00:38:00"),    # idem côté course à pied
        ("Course à pied", "00:40:00"),
    ]
    html = make_detail_html(total_time="02:00:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert raw["cumulative"] is False
    assert result.bike_time == "01:00:00"
    assert result.run_time == "00:40:00"
    assert raw["split_vélo km 85"] == "00:58:00"
    assert raw["split_cap km 14"] == "00:38:00"


def test_parse_detail_km_checkpoint_alone_leaves_slot_empty():
    """
    Si la ligne récapitulative de section manque vraiment (pas encore postée,
    pas seulement en retard sur le pointage), le pointage kilométrique ne doit
    JAMAIS combler le slot principal à sa place : un slot vide est un signal
    honnête d'absence de donnée, un temps partiel serait trompeur (#678).
    """
    splits = [
        ("Natation", "00:15:00"),
        ("T1", "00:02:30"),
        ("Vélo km 85", "00:58:00"),   # seul pointage vélo présent — pas de "Vélo"
    ]
    html = make_detail_html(total_time="01:16:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.bike_time == ""
    assert raw["split_vélo km 85"] == "00:58:00"


def test_parse_detail_run_derived_when_cumulative_and_absent():
    """
    Cas Lacanau sans ligne run : le run est déduit de total - dernier segment mappé.
    Même fixture que le test cumulatif, mais sans ligne T2 pour forcer la dérivation.
    """
    # Natation + Vélo seulement (T1 et T2 absents) — reste cumulatif
    splits = [
        ("Natation", "00:15:00"),   # 900 s
        ("Vélo", "01:20:00"),        # 4800 s  > 900 → cumulatif
    ]
    html = make_detail_html(total_time="02:05:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert raw["cumulative"] is True
    assert result.swim_time == "00:15:00"   # 900 - 0
    assert result.bike_time == "01:05:00"   # 4800 - 900
    assert result.run_time  == "00:45:00"   # 7500 - 4800


# ── Classements ──────────────────────────────────────────────────────────────

def test_parse_detail_rankings():
    """Les classements général, genre et catégorie sont extraits correctement."""
    ranks = [
        ("Classement général", "42 / 150"),
        ("Classement genre", "15 / 70"),
        ("Classement catégorie", "3 / 10"),
    ]
    html = make_detail_html(ranks=ranks)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.rank_overall  == 42
    assert result.rank_gender   == 15
    assert result.rank_category == 3


# ── Méta-ligne : genre / dossard / catégorie / club ──────────────────────────

def test_parse_detail_meta_standard():
    """Méta-ligne standard : M - Dossard N°2141 - V1H - LE MANS TRIATHLON."""
    html = make_detail_html(meta="M - Dossard N°2141 - V1H - LE MANS TRIATHLON")
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.gender     == "M"
    assert result.bib_number == "2141"
    assert result.category   == "V1H"
    assert result.club       == "LE MANS TRIATHLON"


def test_parse_detail_meta_s1_category():
    """Catégories S1H/S2F (regex étendu pour les numéros de série)."""
    html = make_detail_html(meta="F - Dossard N°99 - S1F - TRI CLUB OUEST")
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.gender   == "F"
    assert result.category == "S1F"
    assert result.club     == "TRI CLUB OUEST"


def test_parse_detail_meta_ma2_category():
    """Catégorie MA2 (Masters Age) — cas Swimrun Cote Beaute 2025."""
    html = make_detail_html(meta="M - Dossard N°1016 - MA2 - TRIATHLON CLUB SAUJONNAIS")
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.category == "MA2"
    assert result.club     == "TRIATHLON CLUB SAUJONNAIS"


def test_parse_detail_meta_female_sef():
    html = make_detail_html(meta="F - Dossard N°42 - SEF - NANTES TRIATHLON")
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.gender   == "F"
    assert result.category == "SEF"
    assert result.club     == "NANTES TRIATHLON"


def test_parse_detail_meta_h_gender_alias():
    """Certains systèmes de chronométrage encodent le genre masculin comme 'H' (Homme)."""
    html = make_detail_html(meta="H - Dossard N°77 - V2H - TRIATH CLUB")
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.gender   == "M"   # "H" normalisé en "M"
    assert result.category == "V2H"
    assert result.club     == "TRIATH CLUB"


def test_parse_detail_meta_be_f_spaces():
    """Catégorie avec espace interne ('BE F') → normalisée en 'BEF'."""
    html = make_detail_html(meta="F - Dossard N°5 - BE F - CLUB JUNIORS")
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.category == "BEF"
    assert result.club     == "CLUB JUNIORS"


# ── Duathlon : "CAP 1" → swim_time (run1), "CAP 2" → run_time (run2) ─────────

def test_parse_detail_duathlon_cap1_cap2():
    """
    Duathlon — CAP 1 (1ère course) → swim_time, VELO → bike_time, CAP 2 → run_time.
    Le slot swim_time est réutilisé pour la 1ère fraction de course du duathlon
    car il n'y a pas de natation.
    """
    splits = [
        ("CAP 1", "00:18:00"),
        ("T1", "00:01:00"),
        ("VELO", "00:45:00"),
        ("T2", "00:01:00"),
        ("CAP 2", "00:10:00"),
    ]
    html = make_detail_html(total_time="01:15:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.swim_time == "00:18:00"   # CAP 1 → slot swim
    assert result.t1_time   == "00:01:00"
    assert result.bike_time == "00:45:00"
    assert result.t2_time   == "00:01:00"
    assert result.run_time  == "00:10:00"   # CAP 2 → run
    assert raw["cumulative"] is False


def test_parse_detail_duathlon_course_a_pied_labels():
    """
    Duathlon avec labels 'Course à pied 1' / 'Course à pied 2' (Cesson-Sévigné…).
    Doit mapper run1 → swim_time et run2 → run_time comme CAP 1/CAP 2.
    """
    splits = [
        ("Course à pied 1", "00:20:00"),
        ("T1",               "00:01:00"),
        ("Vélo",             "00:50:00"),
        ("T2",               "00:01:00"),
        ("Course à pied 2",  "00:12:00"),
    ]
    html = make_detail_html(total_time="01:24:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.swim_time == "00:20:00"   # run1 → slot swim
    assert result.t1_time   == "00:01:00"
    assert result.bike_time == "00:50:00"
    assert result.t2_time   == "00:01:00"
    assert result.run_time  == "00:12:00"   # run2 → slot run


def test_parse_detail_duathlon_generic_cap_fallback():
    """
    Si un duathlon utilise juste "CAP" sans numéro, le fallback ("cap", "run") s'applique.
    Splits non cumulatifs (vélo < cap → pas monotone).
    """
    splits = [
        ("CAP", "00:20:00"),    # 1200 s
        ("VELO", "00:05:00"),   # 300 s < 1200 s → non cumulatif
    ]
    html = make_detail_html(total_time="00:25:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert raw["cumulative"] is False
    assert result.run_time  == "00:20:00"
    assert result.bike_time == "00:05:00"


# ── Sables et Cap 2026 : "Transition 1" / "Transition 2" (labels numérotés) ──

def test_parse_detail_transition_numbered_labels():
    """
    Cas Sables et Cap 2026 — T1/T2 labellisés "Transition 1" / "Transition 2".
    Ces labels sont distincts de "Transition Natation" (T1 spécifique), c'est
    la variante générique numérotée. Régression introduite avant l'ajout de
    ("transition 1", "t1") et ("transition 2", "t2") dans la split_map.
    """
    splits = [
        ("Natation",     "00:18:00"),
        ("Transition 1", "00:01:30"),
        ("Vélo",         "01:05:00"),
        ("Transition 2", "00:01:00"),
        ("Course",       "00:42:00"),
    ]
    html = make_detail_html(total_time="02:07:30", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.swim_time == "00:18:00"
    assert result.t1_time   == "00:01:30"
    assert result.bike_time == "01:05:00"
    assert result.t2_time   == "00:01:00"
    assert result.run_time  == "00:42:00"
    assert raw["cumulative"] is False


# ── Mimizan 2026 : "NAT" (forme abrégée, épreuves jeunes) ────────────────────

def test_parse_detail_nat_abbreviated_swim():
    """
    Cas Mimizan 2026 (triathlon-xs-jeunes) — la natation est labellisée "NAT"
    en majuscules abrégées. Régression introduite avant l'ajout de
    ("nat", "swim") dans la split_map.
    """
    splits = [
        ("NAT",  "00:05:32"),
        ("T1",   "00:01:12"),
        ("VELO", "00:16:24"),
        ("T2",   "00:01:03"),
        ("CAP",  "00:10:39"),
    ]
    html = make_detail_html(total_time="00:34:49", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.swim_time == "00:05:32"
    assert result.t1_time   == "00:01:12"
    assert result.bike_time == "00:16:24"
    assert result.t2_time   == "00:01:03"
    assert result.run_time  == "00:10:39"
    assert raw["cumulative"] is False


def test_parse_detail_generic_transition_aquathlon():
    """
    Aquathlon : label "Transition" (sans qualificatif) → t1_time.
    Régression : sans cet entrée, le label était ignoré, seules 2 stages mappées
    (swim+run) étaient détectées comme cumulatives (782 < 1022), produisant un
    run_time erroné (delta cumulatif) au lieu du temps réel.
    """
    splits = [
        ("Natation",    "00:13:02"),   # swim  (782s)
        ("Transition",  "00:00:27"),   # t1    (27s)  ← brise la monotonie → non cumulatif
        ("CAP",         "00:17:02"),   # run   (1022s)
    ]
    html = make_detail_html(total_time="00:30:32", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert raw["cumulative"] is False     # [782, 27, 1022] n'est pas monotone
    assert result.swim_time == "00:13:02"
    assert result.t1_time   == "00:00:27"
    assert result.run_time  == "00:17:02"
    assert result.bike_time == ""


def test_parse_detail_nat_not_matched_as_transition():
    """
    "NAT" ne doit pas être absorbé par ("transition nat", "t1") dont la clé est
    plus longue — seul ("nat", "swim") doit matcher.
    """
    splits = [("NAT", "00:10:00")]
    html = make_detail_html(total_time="00:10:00", splits=splits)
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.swim_time == "00:10:00"
    assert result.t1_time   == ""


# ── _parse_search_row — extraction des lignes de la liste paginée (bulk import)

def _make_search_row(
    bib: str,
    name: str,
    total_time: str = "01:30:00",
    second_truncate: str | None = None,
):
    """Génère un <tr class='result-row'> tel que retourné par resultats-search.jsp."""
    second_cell = f'<td class="truncate">{second_truncate}</td>' if second_truncate else ""
    html = f"""
    <table><tbody>
      <tr class="result-row" data-dossard="{bib}">
        <td class="truncate">{name}</td>
        {second_cell}
        <td class="font-mono">{total_time}</td>
      </tr>
    </tbody></table>
    """
    soup = BeautifulSoup(html, "lxml")
    return soup.select_one("tr.result-row[data-dossard]")


def test_parse_search_row_basic():
    """Extraction du dossard, nom/prénom et temps total depuis une ligne de recherche."""
    row = _make_search_row(bib="995", name="BECT Oscar", total_time="10:57:46")
    result = _parse_search_row(row, "EVT1", "triathlon-xl", "Frenchman 2026", "frenchman-2026", rank=42)

    assert result.bib_number      == "995"
    assert result.athlete_name    == "BECT"
    assert result.athlete_firstname == "Oscar"
    assert result.total_time      == "10:57:46"
    assert result.rank_overall    == 42
    assert result.event_name      == "Frenchman 2026"
    assert result.event_type      == "triathlon-xl"
    assert result.provider        == "klikego"


def test_parse_search_row_multiword_name():
    """Nom composé en majuscules suivi d'un prénom."""
    row = _make_search_row(bib="42", name="LE GALL Pierre")
    result = _parse_search_row(row, "E", "triathlon-m", "Event", "event", rank=1)

    assert result.athlete_name      == "LE GALL"
    assert result.athlete_firstname == "Pierre"


def test_parse_search_row_club_present():
    """Quand une 2ème cellule .truncate est présente, son contenu est le club."""
    row = _make_search_row(
        bib="997",
        name="RINFRAY Julien",
        second_truncate="TRIATHLON CLUB NANTAIS",
    )
    result = _parse_search_row(row, "E", "triathlon-xl", "Frenchman 2026", "frenchman-2026", rank=1)

    assert result.club == "TRIATHLON CLUB NANTAIS"


def test_parse_search_row_city_column():
    """
    Certaines épreuves affichent la ville (ex: 'HERBLAY (95220)') au lieu du club
    dans la 2ème cellule. Ce texte est stocké tel quel — pas de traitement spécial.
    Le filtre city=nantais est utilisé côté API pour l'identification TCN.
    """
    row = _make_search_row(
        bib="17",
        name="YVALUN Johan",
        second_truncate="HERBLAY (95220)",
    )
    result = _parse_search_row(row, "E", "triathlon-xl", "Frenchman 2026", "frenchman-2026", rank=1)

    assert result.club == "HERBLAY (95220)"


def test_parse_search_row_no_second_truncate():
    """Sans 2ème cellule .truncate, le club reste vide."""
    row = _make_search_row(bib="1", name="DUPONT Jean")
    result = _parse_search_row(row, "E", "triathlon-s", "Event", "event", rank=5)

    assert result.club == ""


def test_parse_search_row_source_url():
    """L'URL source est construite depuis event_id, heat et slug."""
    row = _make_search_row(bib="1", name="TEST Athlete")
    result = _parse_search_row(
        row,
        event_id="1700025627600-3",
        heat="triathlon-l-individuel",
        event_name="Event",
        slug="triathlon-dangers-entre-loire-et-maine-2026",
        rank=1,
    )

    assert "1700025627600-3" in result.source_url
    assert "triathlon-l-individuel" in result.source_url
    assert "triathlon-dangers-entre-loire-et-maine-2026" in result.source_url


def _row(html: str):
    return BeautifulSoup(html, "lxml").select_one("tr")


def test_parse_search_row_explicit_status_dnf():
    """La cellule temps porte 'Abandon' → status DNF, total_time vide, rang purgé."""
    html = (
        '<table><tr class="result-row" data-dossard="42">'
        '<td class="truncate">DUPONT Jean</td>'
        '<td class="font-mono">Abandon</td></tr></table>'
    )
    r = _parse_search_row(_row(html), "evt", "heat", "Tri", "slug", 5)
    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None


def test_parse_search_row_finisher_no_status():
    """Cellule temps = vrai temps → status="" et total_time normalisé."""
    html = (
        '<table><tr class="result-row" data-dossard="42">'
        '<td class="truncate">DUPONT Jean</td>'
        '<td class="font-mono">01:23:45</td></tr></table>'
    )
    r = _parse_search_row(_row(html), "evt", "heat", "Tri", "slug", 5)
    assert r.status == ""
    assert r.total_time == "01:23:45"
    assert r.rank_overall == 5


def test_parse_search_row_relay_heat_sets_is_relay():
    """Un heat « ...relais » marque tous les résultats du heat comme relais."""
    row = _make_search_row(bib="12", name="DUPONT Jean")
    result = _parse_search_row(
        row, "EVT1", "triathlon-m-relais", "Tri M", "tri-m", rank=1
    )
    assert result.is_relay is True
    assert result.event_type == "triathlon-m"


def test_parse_search_row_individual_heat_not_relay():
    """Un heat « ...individuel » reste solo."""
    row = _make_search_row(bib="13", name="MARTIN Paul")
    result = _parse_search_row(
        row, "EVT1", "triathlon-m-individuel", "Tri M", "tri-m", rank=1
    )
    assert result.is_relay is False
    assert result.event_type == "triathlon-m"


def test_parse_search_row_duathlon_en_relais_heat():
    """Heat « duathlon-s---en-relais » → relais + event_type duathlon-s."""
    row = _make_search_row(bib="14", name="DURAND Eve")
    result = _parse_search_row(
        row, "EVT1", "duathlon-s---en-relais", "Dua S", "dua-s", rank=1
    )
    assert result.is_relay is True
    assert result.event_type == "duathlon-s"


# ── heat_is_relay — formes d'équipe des heats de la plateforme Klikego (#295)


@pytest.mark.parametrize("heat", [
    "triathlon-s-relais",                     # forme nominale (Vierzon 2026, #203)
    "triathlon-distance-olympique---relais",  # front live.breizhchrono (Dinard 2025)
    "duathlon-s---en-relais",                 # « en relais » — le mot n'est pas en fin
    "swim-run-m-duo",                         # Mesquer 2026 : un duo EST une équipe
    "swim-run-s-duo",
    "swimrun-court-duo",                      # Dinard 2025, front live
    "format-s---en-binome",                   # RE SwimRun 2025 — un binôme aussi
    "format-l---championnat-de-france---en-binome",
    "duathlon-liffre-cormier-clm-par-equipe",  # CLM par équipes
])
def test_heat_is_relay_recognises_observed_team_heats(heat):
    """Les quatre formes d'équipe constatées valent relais au sens du modèle.

    Chacune est tirée d'un événement réel (corpus de classification ci-dessus,
    fixtures Mesquer 2026 et Dinard 2025). Ne connaître que « relais » laissait
    `swim-run-m-duo` en individuel, alors que `is_relay` entre dans l'identité de
    la Course : le duo se retrouvait classé avec les solos.
    """
    assert plat.heat_is_relay(heat) is True


@pytest.mark.parametrize("heat", [
    "triathlon-s-indiv",
    "swim-run-s-indiv",
    "triathlon-m-individuel",
    "swimrun-court-solo",
    "format-m---en-solo",   # RE SwimRun / Côte de Beauté 2025 — l'opposé du binôme
    "duathlon-s",           # la famille « dua- » n'est pas un duo
    "",                     # heat ciblé sans libellé
])
def test_heat_is_relay_leaves_individual_heats_alone(heat):
    """Aucun mot d'équipe → solo. Le test verrouille les formes vues en face."""
    assert plat.heat_is_relay(heat) is False


def test_heat_is_relay_reads_every_signal_it_is_given():
    """Le signal peut venir du slug OU du libellé affiché.

    Un heat ciblé directement n'a pas de libellé (seul le slug parle) ; à
    l'inverse le libellé porte parfois deux formats (« Relais L & Duo »).
    """
    assert plat.heat_is_relay("", "Swim Run M Duo") is True
    assert plat.heat_is_relay("Relais L & Duo") is True
    assert plat.heat_is_relay("", "") is False


def test_heat_is_relay_matches_whole_words_only():
    """Le mot compte comme mot, pas comme sous-chaîne.

    Le heat est un slug tokenisé par tirets : chercher « duo » n'importe où
    dans la chaîne ferait mordre le premier libellé qui contient les trois
    lettres au milieu d'un mot.
    """
    assert plat.heat_is_relay("triathlon-arduo") is False
    assert plat.heat_is_relay("Trophée Iduoret") is False


def test_heat_is_relay_survives_the_accents_of_a_displayed_label():
    """Le slug aplatit les accents, le libellé non : « Binôme », « Équipe ».

    Sans les aplatir, « ô » couperait le mot en deux et le libellé ne dirait
    plus rien — le slug seul portait alors le signal.
    """
    assert plat.heat_is_relay("Format L - En Binôme") is True
    assert plat.heat_is_relay("Duathlon CLM par Équipe") is True


# ── course_name — nom de course partagé Klikego / Breizh Chrono (#308) ───────


def test_course_name_suffixe_le_heat():
    """Le nom de course porte le libellé du heat : deux heats d'une même épreuve
    ne peuvent plus fusionner sur l'identité (nom, date, type, relais)."""
    assert (
        plat.course_name("Triathlon SwimRun Dinard Côte d'Emeraude", "Trail 11 KM")
        == "Triathlon SwimRun Dinard Côte d'Emeraude - Trail 11 KM"
    )


def test_course_name_heat_label_absent_pas_de_suffixe_vide():
    """Heat ciblé sans libellé connu (ex. `scrape_event_all`, contrat historique
    sans discovery) → nom d'épreuve seul, sans tiret ni suffixe vide."""
    assert plat.course_name("Triathlon de Vannes 2025", "") == "Triathlon de Vannes 2025"


def test_course_name_event_name_absent_le_heat_fait_office_de_nom():
    """Nom d'épreuve introuvable → le libellé du heat fait office de nom."""
    assert plat.course_name("", "Trail 11 KM") == "Trail 11 KM"


def test_course_name_compacte_les_espaces_multiples():
    """La plateforme sème des espaces doubles dans ses libellés."""
    assert (
        plat.course_name("Triathlon Découverte  Aésio Mutuelle", "Triathlon  M")
        == "Triathlon Découverte Aésio Mutuelle - Triathlon M"
    )


def test_parse_search_row_duo_heat_sets_is_relay():
    """Mesquer 2026 : `swim-run-m-duo` → relais, comme son voisin « relais »."""
    row = _make_search_row(bib="15", name="LEROY Anne")
    result = _parse_search_row(
        row, "EVT1", "swim-run-m-duo", "Swim Run M Duo", "swimrun-mesquer", rank=1
    )
    assert result.is_relay is True


# ── decode_data_block — décodage du data block base64+XOR ────────────────────


def _encode_block(lines: list[str]) -> str:
    """Encode des lignes comme le fait le fournisseur : XOR 'K' puis base64."""
    payload = "\n".join(lines).encode("utf-8")
    xored = bytes(b ^ ord("K") for b in payload)
    b64 = base64.b64encode(xored).decode("ascii")
    return f'<script type="text/plain" id="data">{b64}</script>'


def test_decode_data_block_returns_split_rows():
    html = _encode_block([
        "358|true|1|1|DE POORTER Axel|S3|M|LE MANS TRIATHLON||00:38:05||",
        "282|false|DNF|DNF|DELAUNAY Juliette|S2|F|||||",
    ])
    rows = decode_data_block(html)
    assert len(rows) == 2
    assert rows[0][0] == "358"
    assert rows[0][4] == "DE POORTER Axel"
    assert rows[0][9] == "00:38:05"
    assert rows[1][2] == "DNF"


def test_decode_data_block_empty_when_no_element():
    assert decode_data_block("<html><body>rien</body></html>") == []


def test_decode_data_block_tolerant_on_invalid_payload():
    # Bloc présent mais base64 corrompu : on ne casse pas l'import, on renvoie [].
    html = '<script type="text/plain" id="data">!!!pas-du-base64!!!</script>'
    assert decode_data_block(html) == []


# ── parse_data_row — transformation d'une ligne du data block en dict ────────


def test_parse_data_row_finisher():
    fields = "358|true|1|1|DE POORTER Axel|S3|M|LE MANS TRIATHLON||00:38:05||".split("|")
    r = parse_data_row(fields)
    assert r["bib_number"] == "358"
    assert r["athlete_name"] == "DE POORTER"
    assert r["athlete_firstname"] == "Axel"
    assert r["category"] == "S3"
    assert r["gender"] == "M"
    assert r["club"] == "LE MANS TRIATHLON"
    assert r["rank_overall"] == 1
    assert r["rank_category"] == 1
    assert r["total_time"] == "00:38:05"
    assert r["status"] == ""


def test_parse_data_row_dnf_neutralises_rank_and_time():
    fields = "282|false|DNF|DNF|DELAUNAY Juliette|S2|F|||||".split("|")
    r = parse_data_row(fields)
    assert r["status"] == "DNF"
    assert r["rank_overall"] is None
    assert r["rank_category"] is None
    assert r["total_time"] == ""
    assert r["athlete_name"] == "DELAUNAY"
    assert r["athlete_firstname"] == "Juliette"


def test_parse_data_row_dns_and_dsq():
    # DNS
    dns_fields = "476|false|DNS|DNS|AVENARD Benedicte|S2|F|||||".split("|")
    dns_result = parse_data_row(dns_fields)
    assert dns_result["status"] == "DNS"
    assert dns_result["rank_overall"] is None
    assert dns_result["rank_category"] is None
    assert dns_result["total_time"] == ""

    # DSQ
    dsq_fields = "375|false|DSQ|DSQ|MOTTAY Aude|V3|F|||||".split("|")
    dsq_result = parse_data_row(dsq_fields)
    assert dsq_result["status"] == "DSQ"
    assert dsq_result["rank_overall"] is None
    assert dsq_result["rank_category"] is None
    assert dsq_result["total_time"] == ""


def test_parse_data_row_dnf_keeps_time_when_present():
    # DNF ayant couru avant d'abandonner : officiel (idx 9) rempli
    fields = "12|false|DNF|DNF|MARTIN Paul|S2|M|CLUB|00:41:10|01:05:00||".split("|")
    r = parse_data_row(fields)
    assert r["status"] == "DNF"
    assert r["total_time"] == "01:05:00"   # temps conservé
    assert r["rank_overall"] is None       # jamais classé
    assert r["rank_category"] is None


def test_parse_data_row_dsq_keeps_time_when_present():
    fields = "34|false|DSQ|DSQ|DURAND Lea|S3|F|CLUB||01:12:30||".split("|")
    r = parse_data_row(fields)
    assert r["status"] == "DSQ"
    assert r["total_time"] == "01:12:30"
    assert r["rank_overall"] is None


def test_parse_data_row_dns_has_no_time():
    fields = "114|false|DNS|DNS|CHAUVET Romain|S4|M|TRIATHLON CLUB NANTAIS||00:00:00||".split("|")
    r = parse_data_row(fields)
    assert r["status"] == "DNS"
    assert r["total_time"] == ""           # un non-partant n'a pas de temps
    assert r["rank_overall"] is None


# ── Fixture réelle page 0 — valide le décodage + parse sur données réelles ───


def test_fixture_page0_contains_dnf_and_finishers():
    html = (FIXTURES / "klikego_datablock_page0.html").read_text()
    rows = [parse_data_row(r) for r in decode_data_block(html)]
    assert len(rows) == 50  # page pleine
    statuses = {r["status"] for r in rows}
    assert "" in statuses  # des finishers
    # au moins un finisher a un temps total non vide
    assert any(r["total_time"] for r in rows if not r["status"])


# ── fetch_heat_rows — pagination via monkeypatch (sans réseau) ───────────────


def test_fetch_heat_rows_paginates_and_stops(monkeypatch):
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()
    # page 1 : moins de 50 lignes -> doit arrêter après
    calls = {"n": 0}

    class FakeResp:
        status_code = 200
        def __init__(self, text): self.text = text

    # Construit une page courte (2 lignes) encodée comme le fournisseur
    short_lines = "\n".join([
        "999|true|51|1|TEST Alpha|S1|M|CLUB X||01:00:00||",
        "998|true|52|2|TEST Beta|S1|M|CLUB Y||01:01:00||",
    ]).encode()
    short_b64 = base64.b64encode(bytes(b ^ ord("K") for b in short_lines)).decode()
    page1 = f'<script id="data">{short_b64}</script>'

    def fake_get(url):
        calls["n"] += 1
        return FakeResp(page0 if "page=0" in url else page1)

    class FakeClient:
        def get(self, url): return fake_get(url)

    rows = plat.fetch_heat_rows("https://x", "evt", "heat", FakeClient())
    assert calls["n"] == 2          # page 0 (pleine) + page 1 (courte) puis stop
    assert len(rows) == 52          # 50 + 2, dédoublonnés


# ── parse_event_name — le nom d'épreuve vient de la page, pas du slug d'URL ──


def test_parse_event_name_klikego_title():
    """Klikego : « {épreuve} - {code postal} - {ville} - Résultats | Klikego »."""
    from app.scrapers.klikego_platform import parse_event_name

    html = (
        "<html><head><title>\n\t\tRun &amp; Bike de Fay de Bretagne 2026 - 44130 - "
        "Fay de bretagne - Résultats | Klikego\n\t</title></head></html>"
    )
    assert parse_event_name(html, heat="") == "Run & Bike de Fay de Bretagne 2026"


def test_parse_event_name_bc_title_strips_heat_label():
    """Breizh Chrono : « Résultats {heat} - {épreuve} - {code postal} - {ville} ».

    Le nom d'épreuve contient lui-même des « - » : on ne peut pas découper
    naïvement. Le libellé de tête est identifié par son slug, égal au heat.
    """
    from app.scrapers.klikego_platform import parse_event_name

    html = (
        "<html><head><title>Résultats Triathlon M individuel - Triathlon d'Angers - "
        "Entre Loire et Maine 2026 - 49000 - Angers</title></head></html>"
    )
    got = parse_event_name(html, heat="triathlon-m-individuel")
    assert got == "Triathlon d'Angers - Entre Loire et Maine 2026"


def test_parse_event_name_generic_page_returns_empty():
    """Page sans contexte d'épreuve (titre générique) → aucun nom inventé.

    `coureur.jsp` sert ce titre : sans le marqueur « - {code postal} - », on
    renverrait « des courses Breizh Chrono » comme nom de course.
    """
    from app.scrapers.klikego_platform import parse_event_name

    html = "<html><head><title>Résultats des courses Breizh Chrono</title></head></html>"
    assert parse_event_name(html, heat="triathlon-m-individuel") == ""


def test_parse_event_name_no_title():
    from app.scrapers.klikego_platform import parse_event_name

    assert parse_event_name("<html><body>rien</body></html>", heat="") == ""


def test_build_heat_results_prefers_page_title_over_url_name(monkeypatch):
    """Le nom de la page prime sur le nom dérivé du slug d'URL (accents, & , casse).

    Cas de la course 103 : une URL `coureur.jsp` n'a pas de slug → l'appelant ne
    peut fournir aucun nom, et la course était persistée sans nom.
    """
    from app.scrapers.klikego_platform import build_heat_results

    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()
    heat_page = (
        "<html><head><title>Résultats Triathlon M individuel - Triathlon d'Angers - "
        "Entre Loire et Maine 2026 - 49000 - Angers</title></head></html>"
    )

    class FakeResp:
        status_code = 200
        def __init__(self, t): self.text = t

    class FakeClient:
        def get(self, url):
            if "inter=&page=0" in url:
                return FakeResp(page0)
            return FakeResp("<html></html>")

    results = build_heat_results(
        base="https://resultats.breizhchrono.com",
        provider="breizhchrono",
        event_id="1700025627600-3",
        heat="triathlon-m-individuel",
        heat_page_html=heat_page,
        event_name="",  # slug absent de l'URL → l'appelant n'a pas de nom
        slug="",
        event_type="triathlon-m",
        source_url="https://resultats.breizhchrono.com/x",
        event_date=None,
        client=FakeClient(),
    )
    assert results
    assert all(
        r.event_name == "Triathlon d'Angers - Entre Loire et Maine 2026" for r in results
    )


def test_build_heat_results_falls_back_to_url_name_without_title():
    """Sans titre exploitable, on conserve le nom fourni par l'appelant (slug)."""
    from app.scrapers.klikego_platform import build_heat_results

    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        status_code = 200
        def __init__(self, t): self.text = t

    class FakeClient:
        def get(self, url):
            return FakeResp(page0 if "inter=&page=0" in url else "<html></html>")

    results = build_heat_results(
        base="https://x", provider="klikego", event_id="1", heat="triathlon-m",
        heat_page_html="<html>pas de titre</html>",
        event_name="Triathlon De Vierzon 2026", slug="triathlon-de-vierzon-2026",
        event_type="triathlon-m", source_url="https://x", event_date=None,
        client=FakeClient(),
    )
    assert all(r.event_name == "Triathlon De Vierzon 2026" for r in results)


def test_build_heat_results_sets_is_relay_on_relay_heats():
    """Un heat dont le slug contient « relais » marque **tous** ses résultats.

    Sans ça, `triathlon-s-indiv` et `triathlon-s-relais` d'un même événement
    (Vierzon 2026, #203) fusionnent en une seule Course via l'UNIQUE
    (name, event_date, event_type, is_relay) — le heat relais est aspiré dans
    l'individuel.
    """
    from app.scrapers.klikego_platform import build_heat_results

    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        status_code = 200
        def __init__(self, t): self.text = t

    class FakeClient:
        def get(self, url):
            return FakeResp(page0 if "inter=&page=0" in url else "<html></html>")

    relais = build_heat_results(
        base="https://x", provider="klikego", event_id="1",
        heat="triathlon-s-relais",
        heat_page_html="<html></html>",
        event_name="Tri", slug="tri", event_type="triathlon-s",
        source_url="https://x", event_date=None, client=FakeClient(),
    )
    indiv = build_heat_results(
        base="https://x", provider="klikego", event_id="1",
        heat="triathlon-s-indiv",
        heat_page_html="<html></html>",
        event_name="Tri", slug="tri", event_type="triathlon-s",
        source_url="https://x", event_date=None, client=FakeClient(),
    )
    assert relais and indiv
    assert all(r.is_relay is True for r in relais)
    assert all(r.is_relay is False for r in indiv)


def test_build_heat_results_sets_is_relay_on_duo_heats():
    """Même exigence pour un duo : `swim-run-s-duo` et `swim-run-s-indiv`
    coexistent à Mesquer 2026, mêmes nom, date et type. Si le duo sort
    `is_relay=False`, les deux heats fusionnent sur l'UNIQUE
    (name, event_date, event_type, is_relay) et le classement mélange les
    équipes aux solos.
    """
    from app.scrapers.klikego_platform import build_heat_results

    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        status_code = 200
        def __init__(self, t): self.text = t

    class FakeClient:
        def get(self, url):
            return FakeResp(page0 if "inter=&page=0" in url else "<html></html>")

    duo = build_heat_results(
        base="https://x", provider="klikego", event_id="1",
        heat="swim-run-s-duo",
        heat_page_html="<html></html>",
        event_name="SwimRun", slug="swimrun-mesquer", event_type="swimrun-s",
        source_url="https://x", event_date=None, client=FakeClient(),
    )
    assert duo
    assert all(r.is_relay is True for r in duo)


# ── discover_inter_options et inter_label_to_slot — découverte des checkpoints


def test_discover_inter_options_triathlon():
    from app.scrapers.klikego_platform import discover_inter_options

    html = '''
    <select name="inter" id="inter">
      <option value="">Arrivée</option>
      <option value="Natation___T1">Natation + T1</option>
      <option value="Vélo">Vélo</option>
      <option value="Course">Course</option>
    </select>'''
    assert discover_inter_options(html) == [
        ("Natation___T1", "Natation + T1"),
        ("Vélo", "Vélo"),
        ("Course", "Course"),
    ]


def test_discover_inter_options_absent():
    from app.scrapers.klikego_platform import discover_inter_options

    assert discover_inter_options("<html>pas de select</html>") == []


def test_inter_label_to_slot():
    from app.scrapers.klikego_platform import inter_label_to_slot

    assert inter_label_to_slot("Natation + T1") == "swim"
    assert inter_label_to_slot("Vélo") == "bike"
    assert inter_label_to_slot("Course") == "run"
    assert inter_label_to_slot("Course à pied 1") == "swim"   # duathlon CAP1 -> slot swim
    assert inter_label_to_slot("Course à pied 2") == "run"    # duathlon CAP2 -> slot run
    assert inter_label_to_slot("Truc inconnu") is None


# ── fetch_inter_splits — collecte des temps intermédiaires pour tous les participants


def _block(lines):
    """Encode des lignes comme le fait le fournisseur : XOR 'K' puis base64."""
    payload = "\n".join(lines).encode()
    return f'<script id="data">{base64.b64encode(bytes(b ^ ord("K") for b in payload)).decode()}</script>'


def test_fetch_inter_splits_collects_per_slot(monkeypatch):
    """Collecte les temps de checkpoints pour tous les participants d'un heat.

    Pour chaque option `inter` mappable sur un slot, pagine le data block et lit
    le champ `inter` (idx 8). Retourne `{bib: {slot: "HH:MM:SS"}}`.
    Les checkpoints dont le label ne mappe sur aucun slot sont ignorés.
    """
    # inter=Vélo : le temps du checkpoint est dans le champ idx 8
    velo = _block(["358|true|1|1|DE POORTER Axel|S3|M|CLUB|00:19:28|||"])
    nat = _block(["358|true|1|1|DE POORTER Axel|S3|M|CLUB|00:06:24|||"])

    class FakeResp:
        status_code = 200
        def __init__(self, t):
            self.text = t

    class FakeClient:
        def get(self, url):
            # La valeur `inter` est désormais URL-encodée (Vélo -> V%C3%A9lo).
            if "inter=V%C3%A9lo" in url:
                return FakeResp(velo)
            if "inter=Natation___T1" in url:
                return FakeResp(nat)
            return FakeResp(_block([]))

    options = [("Natation___T1", "Natation + T1"), ("Vélo", "Vélo")]
    splits = plat.fetch_inter_splits("https://x", "evt", "heat", options, FakeClient())
    assert splits["358"] == {"swim": "00:06:24", "bike": "00:19:28"}


# ── build_heat_results — assemblage des ScrapedResult complets d'un heat ─────


def test_build_heat_results_includes_dnf_and_total_times(monkeypatch):
    """
    build_heat_results pagine le data block et retourne des ScrapedResult complets.

    La fixture page0 est une page « charnière » réelle du heat (50 lignes :
    finishers avec temps + DNF/DSQ/DNS), ce qui couvre les deux chemins.
    """
    from datetime import date

    from app.scrapers.klikego_platform import build_heat_results

    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        status_code = 200
        def __init__(self, t): self.text = t

    class FakeClient:
        def get(self, url):
            # Liste : page 0 pleine puis page vide pour arrêter
            if "inter=&page=0" in url:
                return FakeResp(page0)
            return FakeResp("<html></html>")

    # Pas de checkpoints inter dans ce test -> heat_page_html sans select
    results = build_heat_results(
        base="https://resultats.breizhchrono.com",
        provider="breizhchrono",
        event_id="1488071608761-572",
        heat="triathlon-s-light",
        heat_page_html="<html>pas de inter</html>",
        event_name="Triathlon Audencia La Baule 2024",
        slug="triathlon-audencia-la-baule-2024",
        event_type="triathlon_s",
        source_url="https://resultats.breizhchrono.com/x",
        event_date=date(2024, 9, 28),
        client=FakeClient(),
    )
    assert len(results) == 50
    assert any(r.status == "DNF" for r in results)
    assert any(r.status == "" and r.total_time for r in results)
    assert all(r.provider == "breizhchrono" for r in results)
    assert all(r.event_type == "triathlon_s" for r in results)
    assert all(r.event_date == date(2024, 9, 28) for r in results)


# ── scrape_event_all — import exhaustif via data block (finishers + DNF/DNS/DSQ)


def test_klikego_scrape_event_all_returns_dnf(monkeypatch):
    """
    scrape_event_all doit utiliser le data block (course-result.jsp) pour récupérer
    tous les participants, y compris DNF/DNS/DSQ absents de resultats-search.jsp.

    La fixture page0 contient 50 lignes (finishers + DNF) : le résultat doit en
    avoir exactement 50 et au moins un avec status=="DNF".
    """
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        def __init__(self, t, code=200): self.text, self.status_code = t, code

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url):
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            if "course-result.jsp" in url:
                return FakeResp("<html></html>")
            if "resultats-search.jsp" in url:  # phase TCN city=nantais -> vide
                return FakeResp("<html></html>")
            return FakeResp("<html></html>")

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("triathlon-s-light", None))

    results = klikego.scrape_event_all(
        "1488071608761-572", "triathlon-s-light",
        "Triathlon Audencia La Baule 2024", "triathlon-audencia-la-baule-2024",
    )
    assert len(results) == 50
    assert any(r.status == "DNF" for r in results)


# ── Phase C — les splits fins TCN priment sur les splits inter pré-remplis ───


def test_parse_detail_ignores_zero_placeholders():
    """Page détail d'un non-partant : ignore les placeholders 00:00:00 et rang 0."""
    html = """
    <div><div>Temps Officiel</div><div>00:00:00</div></div>
    <div><div>Classement Général</div><div>0</div></div>
    """
    r = ScrapedResult(source_url="https://x", provider="klikego")
    r.status = "DNS"
    _parse_detail(html, r, {})
    assert r.total_time == ""        # le 00:00:00 placeholder est ignoré
    assert r.rank_overall is None    # le rang 0 est ignoré


def test_scrape_event_all_tcn_detail_overrides_inter_splits(monkeypatch):
    """Phase C : les splits fins de la page détail priment sur les splits inter pré-remplis.

    Sans le reset des slots avant _parse_detail, la règle « first-wins » de
    _parse_detail bloque l'écriture du split fin quand le slot est déjà rempli
    par la valeur inter (ex. Natation___T1 → swim_time = 00:10:00).
    Avec le reset, _parse_detail repeuple intégralement et swim_time vaut 00:06:24.
    """
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    # Data block inter=Natation___T1 : bib 422 a 00:10:00 en idx 8 (valeur inter combinée nat+T1)
    natation_inter_block = _block(["422|true|1|1|CASE Kay|V6|F||00:10:00|||"])

    heat_page_html = """
    <html><body>
      <select name="inter" id="inter">
        <option value="">Arrivée</option>
        <option value="Natation___T1">Natation + T1</option>
      </select>
    </body></html>
    """

    nantais_search_html = """
    <html><body><table><tbody>
      <tr class="result-row" data-dossard="422">
        <td class="truncate">CASE Kay</td>
        <td class="font-mono">01:14:31</td>
      </tr>
    </tbody></table></body></html>
    """

    # Page détail bib 422 : split natation FIN différent (00:06:24 ≠ 00:10:00 inter)
    detail_html = make_detail_html(
        meta="F - Dossard N°422 - V6 - TRIATHLON CLUB NANTAIS",
        total_time="01:14:31",
        splits=[
            ("Natation", "00:06:24"),
            ("T1",        "00:01:30"),
            ("Vélo",      "00:35:00"),
            ("T2",        "00:01:00"),
            ("Course",    "00:31:07"),
        ],
    )

    class FakeResp:
        def __init__(self, t, code=200):
            self.text, self.status_code = t, code

    nantais_calls = {"n": 0}

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def get(self, url):
            # Heat page : contient le <select name="inter"> avec Natation___T1
            if "klikego.com/resultats/" in url and "heat=" in url:
                return FakeResp(heat_page_html)
            # course-result.jsp : liste principale (inter=vide, page 0)
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            # course-result.jsp : splits inter Natation___T1 → bib 422 a 00:10:00
            if "course-result.jsp" in url and "inter=Natation___T1" in url:
                return FakeResp(natation_inter_block)
            # course-result.jsp : autres pages → stop pagination
            if "course-result.jsp" in url:
                return FakeResp("<html></html>")
            # TCN search city=nantais : bib 422 à la 1ère page, vide ensuite
            if "resultats-search.jsp" in url and "city=nantais" in url:
                nantais_calls["n"] += 1
                return FakeResp(nantais_search_html if nantais_calls["n"] == 1 else "<html></html>")
            # Page détail bib 422 : split natation FIN = 00:06:24
            if "resultat-participant.jsp" in url and "dossard=422" in url:
                return FakeResp(detail_html)
            return FakeResp("<html></html>")

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("triathlon-s-light", None))

    results = klikego.scrape_event_all(
        "1488071608761-572", "triathlon-s-light",
        "Triathlon Test 2024", "triathlon-test-2024",
    )

    r422 = next(r for r in results if r.bib_number == "422")
    # Sans le reset (avant fix) : swim_time resterait "00:10:00" (valeur inter pré-remplie)
    # Avec le reset (après fix)  : swim_time = "00:06:24" (valeur fine de la page détail)
    assert r422.swim_time == "00:06:24", (
        f"Les splits fins TCN doivent primer sur les splits inter. "
        f"swim_time={r422.swim_time!r} (attendu '00:06:24')."
    )


def test_scrape_event_all_fetches_detail_for_non_tcn(monkeypatch):
    """Phase C : la page détail est récupérée pour TOUS les participants, pas seulement les TCN.

    Le bib 182 (BELATTAR Claudine) n'a aucun club et n'apparaît pas dans la
    recherche city=nantais : sous l'ancienne logique il n'aurait aucun split.
    Avec le correctif, sa page détail alimente ses splits fins.
    """
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    detail_182 = make_detail_html(
        meta="F - Dossard N°182 - V3 - ST NAZAIRE",
        total_time="01:14:35",
        splits=[
            ("Natation", "00:16:24"),
            ("Vélo",     "00:31:00"),
            ("Course",   "00:08:55"),
        ],
    )

    class FakeResp:
        def __init__(self, t, code=200): self.text, self.status_code = t, code

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url):
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            if "course-result.jsp" in url:
                return FakeResp("<html></html>")
            if "resultats-search.jsp" in url:  # aucun TCN (city=nantais vide)
                return FakeResp("<html></html>")
            if "resultat-participant.jsp" in url and "dossard=182" in url:
                return FakeResp(detail_182)
            if "resultat-participant.jsp" in url:  # autres bibs : détail sans splits
                return FakeResp("<html></html>")
            return FakeResp("<html></html>")

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("triathlon-s-light", None))

    results = klikego.scrape_event_all(
        "1488071608761-572", "triathlon-s-light",
        "Triathlon Audencia La Baule 2024", "triathlon-audencia-la-baule-2024",
    )

    r182 = next(r for r in results if r.bib_number == "182")
    assert r182.swim_time == "00:16:24"
    assert r182.bike_time == "00:31:00"
    assert r182.run_time == "00:08:55"


def test_scrape_event_all_phase_c_paralleles_avec_plafond(monkeypatch):
    """Phase C : les requêtes de détail partent en parallèle, plafonnées (#583).

    Sonde thread-safe : compte la concurrence effective des GET vers
    resultat-participant.jsp. Une boucle séquentielle ne dépasserait jamais 1.
    """
    import threading
    import time

    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    concurrency = {"current": 0, "peak": 0}
    lock = threading.Lock()

    class FakeResp:
        def __init__(self, t, code=200):
            self.text, self.status_code = t, code

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def get(self, url):
            if "resultat-participant.jsp" in url:
                with lock:
                    concurrency["current"] += 1
                    concurrency["peak"] = max(concurrency["peak"], concurrency["current"])
                time.sleep(0.05)
                with lock:
                    concurrency["current"] -= 1
                return FakeResp("<html></html>")
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            if "course-result.jsp" in url:
                return FakeResp("<html></html>")
            if "resultats-search.jsp" in url:
                return FakeResp("<html></html>")
            return FakeResp("<html></html>")

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("triathlon-s-light", None))

    klikego.scrape_event_all(
        "1488071608761-572", "triathlon-s-light",
        "Triathlon Test 2024", "triathlon-test-2024",
    )

    assert concurrency["peak"] > 1, (
        f"les requêtes de détail devraient partir en parallèle, pic={concurrency['peak']}"
    )
    assert concurrency["peak"] <= 10, f"plafond de 10 workers dépassé : pic={concurrency['peak']}"


def test_scrape_event_all_phase_c_ignore_les_echecs_reseau_par_participant(monkeypatch, caplog):
    """Un GET de détail qui lève (réseau) ne fait pas échouer tout le heat (#583).

    Avant ce correctif, l'exception remontait par `future.result()` et faisait
    échouer `_scrape_single_heat` — mais `ThreadPoolExecutor.__exit__` (sans
    `cancel_futures`) attend d'abord que **toutes** les tâches déjà soumises se
    terminent, donc un flake sur un gros heat aurait payé le coût de la
    quasi-totalité des requêtes avant d'abandonner. Le participant en échec
    garde ses splits de phase B (inter, non écrasés) ; les autres reçoivent
    leurs splits fins normalement.
    """
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    detail_182 = make_detail_html(
        meta="F - Dossard N°182 - V3 - ST NAZAIRE",
        total_time="01:14:35",
        splits=[
            ("Natation", "00:16:24"),
            ("Vélo",     "00:31:00"),
            ("Course",   "00:08:55"),
        ],
    )

    class FakeResp:
        def __init__(self, t, code=200):
            self.text, self.status_code = t, code

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def get(self, url):
            if "resultat-participant.jsp" in url and "dossard=422" in url:
                raise httpx.ConnectError("boom")
            if "resultat-participant.jsp" in url and "dossard=182" in url:
                return FakeResp(detail_182)
            if "resultat-participant.jsp" in url:
                return FakeResp("<html></html>")
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            if "course-result.jsp" in url:
                return FakeResp("<html></html>")
            if "resultats-search.jsp" in url:
                return FakeResp("<html></html>")
            return FakeResp("<html></html>")

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("triathlon-s-light", None))

    import logging as _log
    with caplog.at_level(_log.WARNING, logger="app.scrapers.klikego"):
        results = klikego.scrape_event_all(
            "1488071608761-572", "triathlon-s-light",
            "Triathlon Test 2024", "triathlon-test-2024",
        )

    r422 = next(r for r in results if r.bib_number == "422")
    r182 = next(r for r in results if r.bib_number == "182")

    assert r422 is not None, "le participant en échec réseau reste dans le résultat"
    assert r182.swim_time == "00:16:24", "182 doit recevoir ses splits fins malgré l'échec de 422"
    assert any("422" in rec.message for rec in caplog.records), "l'échec réseau doit être journalisé"


def test_scrape_event_fanout_on_detail_progress_notifie_pendant_la_phase_c(monkeypatch):
    """`on_detail_progress` rapporte l'avancement dans la phase C d'un heat (#583).

    Sans lui, la progression SSE reste figée sur tout un heat (jusqu'à ~4 min
    sur 250 participants) : elle doit être notifiée par lot, pas seulement une
    fois par heat comme `on_heat_start`.
    """
    event_html = load_klikego_fixture("mesquer-2026-event.html")
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        def __init__(self, text: str, code: int = 200):
            self.text, self.status_code = text, code

    class FakeClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False

        def get(self, url: str):
            if "course-result.jsp" in url:
                if "inter=&page=0" in url:
                    return FakeResp(page0)
                return FakeResp("<html></html>")
            if "resultats-search.jsp" in url:
                return FakeResp("<html></html>")
            if "resultat-participant.jsp" in url:
                return FakeResp("<html></html>")
            if "?heat=" in url:
                return FakeResp("<html></html>")
            return FakeResp(event_html)

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("", None))

    # Ne laisser passer qu'un seul heat, sans quoi les 50 requêtes de détail
    # de page0 se répéteraient sur les 8 heats de la fixture.
    def probe(heat_url: str) -> bool:
        return "?heat=triathlon-s-indiv" not in heat_url

    notifications: list[tuple[str, int, int, int, int]] = []

    def on_detail_progress(heat_slug, heat_label, heat_index, heats_total, done, total):
        notifications.append((heat_slug, heat_index, heats_total, done, total))

    klikego.scrape_event_fanout(
        "1677015306084-12", "Mesquer", "triathlon-et-swimrun-mesquer-quimiac-2026",
        cache_probe=probe, on_detail_progress=on_detail_progress,
    )

    assert notifications, "la phase C d'un heat de 50 participants doit notifier au moins une fois"
    assert all(n[0] == "triathlon-s-indiv" for n in notifications)
    assert all(n[1] == 1 and n[2] == 1 for n in notifications), "seul heat non-caché : index 1/1"
    assert notifications[-1][3] == notifications[-1][4] == 50, "la dernière notification couvre la totalité"
    assert len(notifications) < 50, "notifié par lot, pas à chaque participant"


# ── _enumerate_heats — fan-out event (issue #156) ────────────────────────────


def test_enumerate_heats_mesquer():
    """Cas nominal — page événement Mesquer 2026, 8 heats publiés."""
    html = load_klikego_fixture("mesquer-2026-event.html")
    heats = klikego._enumerate_heats(html)

    assert len(heats) == 8, f"attendu 8 heats, obtenu {len(heats)}"
    slugs = [slug for slug, _ in heats]
    assert "triathlon-s-indiv" in slugs
    assert "swim-run-m-duo" in slugs
    # Ordre du DOM préservé
    assert heats[0][0] == "swim-run-m-duo"
    # Libellés lisibles (span)
    labels_by_slug = dict(heats)
    assert labels_by_slug["triathlon-s-indiv"] == "Triathlon S Indiv"
    assert labels_by_slug["swim-run-m-duo"] == "Swim Run M Duo"


def test_enumerate_heats_ignores_empty_value_placeholder():
    """Nozéen — le <el-select> contient une option value="" (placeholder « choisir »)
    en plus des 4 vrais heats. On ne doit pas la retourner."""
    html = load_klikego_fixture("nozeen-2025-event.html")
    heats = klikego._enumerate_heats(html)

    slugs = [slug for slug, _ in heats]
    assert "" not in slugs, "placeholder value=\"\" ne doit pas apparaître"
    assert len(heats) == 4
    assert "duathlon-s---en-individuel-open---non-selectif" in slugs


def test_enumerate_heats_no_select():
    """Page sans <el-select name="heat"> (inscription, challenge, événement non chronométré)."""
    html = load_klikego_fixture("no-select.html")
    assert klikego._enumerate_heats(html) == []


def test_enumerate_heats_empty_string():
    assert klikego._enumerate_heats("") == []


def test_enumerate_heats_select_without_options():
    """<el-select> présent mais aucune <el-option> à l'intérieur."""
    html = '<html><body><el-select name="heat"></el-select></body></html>'
    assert klikego._enumerate_heats(html) == []


# ── scrape_event_fanout — fan-out avec cache_probe et failures (issue #156) ──


def _make_fanout_fake_client(monkeypatch, event_html: str, heat_bibs: dict | None = None):
    """Monkeypatch httpx.Client pour rendre l'événement + heats mockés.

    heat_bibs : {heat_slug: list_of_bibs} — chaque bib retourne un ScrapedResult
    minimal via une page heat vide et un data-block synthétique. Par défaut,
    rend une liste vide de participants par heat.
    """
    heat_bibs = heat_bibs or {}
    calls = {"event_page": 0, "heat_page": [], "detail": []}

    class FakeResp:
        def __init__(self, text: str, code: int = 200):
            self.text = text
            self.status_code = code

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, url: str, *a, **k):
            if "resultats" in url and "?heat=" not in url:
                # Page événement
                calls["event_page"] += 1
                return FakeResp(event_html)
            if "?heat=" in url and "resultat-participant" not in url:
                # Page heat — on renvoie vide, la logique de parsing se contentera d'une liste vide
                calls["heat_page"].append(url)
                return FakeResp("<html></html>")
            if "resultat-participant.jsp" in url:
                calls["detail"].append(url)
                return FakeResp("<html></html>")
            return FakeResp("", 404)

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("", None))
    return calls


def test_scrape_event_fanout_nominal_returns_trace(monkeypatch):
    """Fan-out sans cache_probe : les 8 heats énumérés remontent une trace complète."""
    html = load_klikego_fixture("mesquer-2026-event.html")
    calls = _make_fanout_fake_client(monkeypatch, html)

    results, trace = klikego.scrape_event_fanout(
        "1677015306084-12", "Mesquer 2026", "triathlon-et-swimrun-mesquer-quimiac-2026",
    )

    assert trace.heats_enumerated == 8
    assert trace.heats_cached == 0
    assert trace.heats_imported == 0  # dérivé côté import_service
    assert trace.failures == []
    # Les 8 pages de heat sont GET (chaque heat scrapé, même si résultats vides)
    assert len(calls["heat_page"]) == 8


def test_scrape_event_fanout_cache_probe_skips_heats(monkeypatch):
    """cache_probe qui retourne True pour 3 heats → seuls 5 sont scrapés."""
    html = load_klikego_fixture("mesquer-2026-event.html")
    calls = _make_fanout_fake_client(monkeypatch, html)

    cached_slugs = {"swim-run-m-duo", "triathlon-s-indiv", "triathlon-xs-relais"}
    def probe(heat_url: str) -> bool:
        return any(f"?heat={s}" in heat_url for s in cached_slugs)

    results, trace = klikego.scrape_event_fanout(
        "1677015306084-12", "Mesquer", "triathlon-et-swimrun-mesquer-quimiac-2026",
        cache_probe=probe,
    )

    assert trace.heats_enumerated == 8
    assert trace.heats_cached == 3
    assert trace.failures == []
    assert len(calls["heat_page"]) == 5  # seuls les 5 non-cachés sont GET


def test_scrape_event_fanout_heat_failure_isolated(monkeypatch, caplog):
    """Un heat qui lève ne casse pas les autres — sa cause est capturée dans trace.failures."""
    html = load_klikego_fixture("mesquer-2026-event.html")
    _make_fanout_fake_client(monkeypatch, html)

    from app.scrapers import klikego as kli_mod
    original = kli_mod._scrape_single_heat

    def flaky(event_id, heat, heat_label, event_name, slug, event_date, client, **kwargs):
        if heat == "triathlon-xs-relais":
            raise RuntimeError("boom on xs-relais")
        return original(event_id, heat, heat_label, event_name, slug, event_date, client, **kwargs)

    monkeypatch.setattr(kli_mod, "_scrape_single_heat", flaky)

    import logging as _log
    with caplog.at_level(_log.WARNING, logger="app.scrapers.klikego"):
        results, trace = klikego.scrape_event_fanout(
            "1677015306084-12", "Mesquer", "triathlon-et-swimrun-mesquer-quimiac-2026",
        )

    assert trace.heats_enumerated == 8
    assert len(trace.failures) == 1
    assert trace.failures[0]["heat_slug"] == "triathlon-xs-relais"
    assert "boom on xs-relais" in trace.failures[0]["reason"]
    assert any("triathlon-xs-relais" in rec.message for rec in caplog.records)


def test_scrape_event_fanout_no_heats_returns_empty(monkeypatch):
    """Page sans <el-select> — retour ([], trace vide)."""
    html = load_klikego_fixture("no-select.html")
    _make_fanout_fake_client(monkeypatch, html)

    results, trace = klikego.scrape_event_fanout("bogus-1", "Bogus", "bogus")

    assert results == []
    assert trace.heats_enumerated == 0
    assert trace.failures == []


def test_scrape_event_fanout_on_heat_start_notifie_par_heat_non_cache(monkeypatch):
    """`on_heat_start` est appelé avant chaque heat effectivement scrapé.

    Trois heats cachés → 5 notifications, index 1..5 sur un total 5, jamais
    sur les 3 sautés. Sans quoi la progression côté front paraîtrait sauter
    des indices (« épreuve 6/8 » alors qu'on scrape la 3e).
    """
    html = load_klikego_fixture("mesquer-2026-event.html")
    _make_fanout_fake_client(monkeypatch, html)

    cached_slugs = {"swim-run-m-duo", "triathlon-s-indiv", "triathlon-xs-relais"}
    def probe(heat_url: str) -> bool:
        return any(f"?heat={s}" in heat_url for s in cached_slugs)

    notifications: list[tuple[str, str, int, int]] = []
    def on_heat_start(heat_slug, heat_label, index, total):
        notifications.append((heat_slug, heat_label, index, total))

    klikego.scrape_event_fanout(
        "1677015306084-12", "Mesquer", "triathlon-et-swimrun-mesquer-quimiac-2026",
        cache_probe=probe, on_heat_start=on_heat_start,
    )

    assert len(notifications) == 5, "un appel par heat scrapé, pas par heat énuméré"
    assert [n[2] for n in notifications] == [1, 2, 3, 4, 5]
    assert all(n[3] == 5 for n in notifications)
    assert not any(n[0] in cached_slugs for n in notifications)


def test_scrape_event_fanout_heats_de_meme_type_restent_distincts(monkeypatch):
    """Deux heats classés `triathlon`/non-relais mais de libellés différents ne
    doivent plus fusionner sur l'identité de Course (#308).

    Mesuré sur Mesquer 2026 : `triathlon-poussin-et-mini-poussin-6-9-ans` et
    `triathlon-pupilles-10-11-ans` partagent le même event_type (`triathlon`) et
    le même is_relay (False). Avant #308, `event_name` était identique pour les
    deux (le nom nu de l'épreuve) : les deux heats fusionnaient sur (nom, date,
    type, relais) et un dossard réutilisé d'un heat à l'autre réattribuait
    silencieusement un résultat à un autre athlète. Le libellé du heat doit
    désormais suffixer `event_name`, exactement comme Breizh Chrono le fait déjà
    (`klikego_platform.course_name`).
    """
    event_html = load_klikego_fixture("mesquer-2026-event.html")
    page0 = (FIXTURES / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        def __init__(self, text: str, code: int = 200):
            self.text, self.status_code = text, code

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, url: str, *a, **k):
            if "course-result.jsp" in url:
                # Première page (sans inter) : renvoie 50 lignes de données.
                # Toute autre page/inter : liste vide → coupe la pagination.
                if "inter=&" in url and "page=0" in url:
                    return FakeResp(page0)
                return FakeResp("<html></html>")
            if "resultat-participant.jsp" in url:
                return FakeResp("<html></html>")
            if "?heat=" in url:
                # Page heat : ni titre ni options inter, pour isoler le libellé
                # de heat comme seule source du suffixe testé ici.
                return FakeResp("<html></html>")
            return FakeResp(event_html)  # page événement (racine)

    monkeypatch.setattr(klikego.httpx, "Client", FakeClient)
    monkeypatch.setattr(klikego, "_fetch_event_meta", lambda *a, **k: ("", None))

    results, _trace = klikego.scrape_event_fanout(
        "1677015306084-12", "Triathlon et Swimrun Mesquer Quimiac 2026",
        "triathlon-et-swimrun-mesquer-quimiac-2026",
    )

    poussin_names = {
        r.event_name for r in results
        if r.raw_data.get("heat_slug") == "triathlon-poussin-et-mini-poussin-6-9-ans"
    }
    pupilles_names = {
        r.event_name for r in results
        if r.raw_data.get("heat_slug") == "triathlon-pupilles-10-11-ans"
    }

    assert poussin_names, "le heat poussin doit produire des résultats"
    assert pupilles_names, "le heat pupilles doit produire des résultats"
    assert poussin_names.isdisjoint(pupilles_names), (
        "les deux heats partagent event_type=triathlon et is_relay=False : "
        "sans le libellé de heat dans event_name, ils fusionnent sur l'identité "
        "de Course (#308)"
    )
    assert poussin_names == {
        "Triathlon et Swimrun Mesquer Quimiac 2026 - "
        "Triathlon Poussin et mini poussin (6-9 ans)"
    }
    assert pupilles_names == {
        "Triathlon et Swimrun Mesquer Quimiac 2026 - Triathlon Pupilles (10-11 ans)"
    }

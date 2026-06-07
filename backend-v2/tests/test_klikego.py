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
"""
import pytest
from bs4 import BeautifulSoup

from app.scrapers.base import ScrapedResult
from app.scrapers.klikego import _detect_event_type, _parse_detail, _parse_search_row

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _detect_event_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("heat,slug,expected", [
    # --- Triathlon (non-régression) ---
    ("triathlon-s", "", "triathlon-s"),
    ("triathlon-s-individuel", "", "triathlon-s"),
    # Lac au Duc : heat auto-détecté comme "format-s-en-individuel"
    ("format-s-en-individuel", "", "triathlon-s"),
    ("triathlon-m", "", "triathlon-m"),
    # Domino : "triathlon-m---individuel"
    ("triathlon-m---individuel", "", "triathlon-m"),
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
    # Mimizan jeunes : heat "triathlon-xs-jeunes" → triathlon-s (xs = extra-short)
    ("triathlon-xs-jeunes", "", "triathlon-s"),
    # heat vide → valeur brute retournée
    ("", "", "triathlon"),
])
def test_event_type_detection(heat, slug, expected):
    assert _detect_event_type(heat, slug) == expected


# ---------------------------------------------------------------------------
# Redon Sprint : pas de splits, juste le temps total
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Domino : "Chg Nat." → t1, "Chg Vé." → t2
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Lacanau : temps cumulés détectés et convertis en déltas
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Classements
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Méta-ligne : genre / dossard / catégorie / club
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Duathlon : "CAP 1" → swim_time (run1), "CAP 2" → run_time (run2)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Sables et Cap 2026 : "Transition 1" / "Transition 2" (labels numérotés)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Mimizan 2026 : "NAT" (forme abrégée, épreuves jeunes)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _parse_search_row — extraction des lignes de la liste paginée (bulk import)
# ---------------------------------------------------------------------------

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

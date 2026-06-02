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
"""
import pytest

from scrapers.base import ScrapedResult
from scrapers.klikego import _detect_event_type, _parse_detail


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
    # --- Duathlon : doit passer AVANT les checks -s/-m (bug corrigé) ---
    ("duathlon-classique", "", "duathlon"),
    ("duathlon-s-individuel", "", "duathlon"),   # était détecté "triathlon-s" avant fix
    ("duathlon-liffre-cormier-open--sprint-court", "", "duathlon"),
    # --- Swimrun : détection via slug (heats = "format-l-en-binome" etc.) ---
    ("swimrun-classique", "", "swimrun"),
    ("format-l---en-binome", "re-swimrun-2025", "swimrun"),       # slug contient "swimrun"
    ("format-m---en-solo", "swimrun-cote-beaute-2025", "swimrun"),
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


def test_parse_detail_meta_female_sef():
    html = make_detail_html(meta="F - Dossard N°42 - SEF - NANTES TRIATHLON")
    result, raw = fresh_result()

    _parse_detail(html, result, raw)

    assert result.gender   == "F"
    assert result.category == "SEF"
    assert result.club     == "NANTES TRIATHLON"


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

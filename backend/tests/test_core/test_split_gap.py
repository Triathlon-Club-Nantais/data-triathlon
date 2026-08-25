"""Tests de la règle d'écart total/somme des inters (#486, RES-10).

Le point de vérité des seuils est le sondage
`docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md` : le seuil de 2 %
proposé par l'audit signalait 8,02 % du classement, dont 285 lignes d'une épreuve saine.
Ces tests figent la règle qui l'a remplacé.
"""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import split_gap


def _row(*, total="01:00:00", splits=None, event_type="triathlon-m", is_relay=False):
    return SimpleNamespace(
        total_time=total,
        splits=splits,
        course=SimpleNamespace(event_type=event_type, is_relay=is_relay),
    )


#: Un triathlon dont les inters somment exactement au total (3600 s).
TRIATHLON_EXACT = {
    "swim": "00:15:00",
    "t1": "00:02:00",
    "bike": "00:30:00",
    "t2": "00:03:00",
    "run": "00:10:00",
}


# ── Évaluabilité : les cinq conditions cumulatives (FR-010) ──────────────────


def test_ratio_is_none_for_a_relay():
    """La somme des inters d'un relayeur ne se compare pas à son temps."""
    row = _row(splits=TRIATHLON_EXACT, is_relay=True)
    assert split_gap.ratio(row) is None


def test_ratio_is_none_without_splits():
    assert split_gap.ratio(_row(splits=None)) is None
    assert split_gap.ratio(_row(splits={})) is None


def test_ratio_is_none_when_a_schema_key_is_missing():
    """Le schéma triathlon attend cinq segments ; quatre ne suffisent pas."""
    partial = dict(TRIATHLON_EXACT)
    del partial["t2"]
    assert split_gap.ratio(_row(splits=partial)) is None


def test_ratio_is_none_when_the_total_is_unreadable_or_zero():
    assert split_gap.ratio(_row(total=None, splits=TRIATHLON_EXACT)) is None
    assert split_gap.ratio(_row(total="", splits=TRIATHLON_EXACT)) is None
    assert split_gap.ratio(_row(total="00:00:00", splits=TRIATHLON_EXACT)) is None


def test_ratio_is_none_when_a_split_is_unreadable():
    """Le cas réel de la course 340, pour lequel #472 a posé la garde d'affichage."""
    broken = dict(TRIATHLON_EXACT, t1="0-2:-15:00")
    assert split_gap.ratio(_row(splits=broken)) is None


def test_unreadable_split_is_rejected_like_the_frontend_does():
    """`to_seconds(strict=True)` rendrait 900 sur « 0-2:-15:00 » — il fait un `search`.

    L'écran, lui, rejette la chaîne (`secondsFromHms`, garde de #472). Les deux côtés
    doivent s'accorder, sans quoi le serveur évalue une ligne que l'écran affiche « — ⚠ ».
    """
    assert split_gap.parse_duration("0-2:-15:00") is None
    assert split_gap.parse_duration("01:23:45.6") is None
    assert split_gap.parse_duration("00:99:00") is None
    assert split_gap.parse_duration("01:02:03") == 3723
    assert split_gap.parse_duration("2:30") == 150


# ── Le calcul lui-même ───────────────────────────────────────────────────────


def test_ratio_is_zero_when_the_splits_sum_to_the_total():
    assert split_gap.ratio(_row(splits=TRIATHLON_EXACT)) == pytest.approx(0.0)


def test_ratio_is_positive_when_a_segment_is_not_published():
    """Signe positif : le total couvre plus que la somme — signature d'un segment absent.

    81,7 % des écarts mesurés sont de ce signe (sondage, § Mesure 2).
    """
    short = dict(TRIATHLON_EXACT, t1="00:01:00")  # 60 s de moins
    assert split_gap.ratio(_row(splits=short)) == pytest.approx(60 / 3600)


def test_ratio_is_negative_when_the_splits_exceed_the_total():
    """Signe négatif : aucune explication bénigne, contrairement au positif."""
    long = dict(TRIATHLON_EXACT, run="00:20:00")  # 600 s de plus
    assert split_gap.ratio(_row(splits=long)) == pytest.approx(-600 / 3600)


def test_the_aquathlon_schema_has_no_transition():
    """C'est ce qui produit les +11,4 % de médiane de la course 65 : la T1 n'y est pas."""
    row = _row(splits={"swim": "00:02:00", "run": "00:02:30"}, event_type="aquathlon")
    # 270 s d'inters pour 300 s de total : les 30 s de transition manquent.
    assert split_gap.ratio(_row(total="00:05:00", splits=row.splits, event_type="aquathlon")) == (
        pytest.approx(30 / 300)
    )


# ── Captation : le cas qui a motivé RES-10 (SC-004) ──────────────────────────


def test_course_214_head_of_ranking_is_flagged():
    """Le seul cas de captation dont on dispose — il ne vit pas dans la base de dev.

    Course 214, premier du classement : natation 00:00:31, vélo 00:00:34,
    course 00:19:18 pour un total de 01:06:18. Les inters ne se rapprochent même pas
    du total. Si ce test tombe, la règle a cessé de capter ce pour quoi elle existe.
    """
    row = _row(
        total="01:06:18",
        splits={
            "swim": "00:00:31",
            "t1": "00:00:00",
            "bike": "00:00:34",
            "t2": "00:00:00",
            "run": "00:19:18",
        },
    )
    ratio = split_gap.ratio(row)

    assert ratio is not None
    assert ratio == pytest.approx(0.693, abs=0.001)
    # Signalée quelle que soit la médiane plausible de son épreuve.
    assert split_gap.is_outlier(ratio, median=0.0, evaluated_rows=498, total_seconds=3978)


# ── La médiane d'épreuve, et le verdict de ligne ─────────────────────────────


def test_median_ignores_unevaluable_rows():
    rows = [
        _row(splits=TRIATHLON_EXACT),
        _row(splits=dict(TRIATHLON_EXACT, t1="00:01:00")),
        _row(splits=None),
        _row(splits=TRIATHLON_EXACT, is_relay=True),
    ]
    assert split_gap.median([split_gap.ratio(r) for r in rows]) == pytest.approx(
        (0.0 + 60 / 3600) / 2
    )


def test_median_is_none_without_any_evaluable_row():
    assert split_gap.median([None, None]) is None
    assert split_gap.median([]) is None


def test_a_row_matching_its_peers_is_not_flagged():
    """Le cœur du sondage : un écart partagé par toute l'épreuve n'est pas une anomalie."""
    assert not split_gap.is_outlier(0.0744, median=0.0744, evaluated_rows=13, total_seconds=500)


def test_a_row_is_flagged_only_beyond_five_percent_from_the_median():
    assert not split_gap.is_outlier(0.05, median=0.0, evaluated_rows=100, total_seconds=3600)
    assert split_gap.is_outlier(0.06, median=0.0, evaluated_rows=100, total_seconds=3600)


def test_small_events_are_never_flagged():
    """Sous 10 lignes évaluables, la médiane n'a pas de sens (course 65 : 9 enfants)."""
    assert not split_gap.is_outlier(0.20, median=0.0, evaluated_rows=9, total_seconds=3600)


def test_a_gap_under_sixty_seconds_is_never_flagged():
    """Sans plancher, un petit dénominateur suffit à franchir 5 %."""
    # 10 % de 300 s = 30 s : au-dessus du seuil relatif, sous le plancher absolu.
    assert not split_gap.is_outlier(0.10, median=0.0, evaluated_rows=50, total_seconds=300)
    assert split_gap.is_outlier(0.10, median=0.0, evaluated_rows=50, total_seconds=3600)


def test_is_outlier_is_false_without_a_median():
    assert not split_gap.is_outlier(0.5, median=None, evaluated_rows=100, total_seconds=3600)


# ── La garde de la dérogation au Principe VI (T007) ──────────────────────────


def test_python_and_typescript_share_the_same_segment_schemas():
    """La duplication du schéma est assumée en §Complexity Tracking — **par ce test**.

    Le plan justifie d'écrire les cinq listes de clés en Python alors qu'elles existent
    déjà en TypeScript, au motif que la règle d'écart doit avoir un domicile unique.
    Cette justification ne tient que si les deux tables ne peuvent pas diverger en
    silence. Le test échoue si le fichier front est introuvable : la garde ne se saute pas.
    """
    source = Path(__file__).parents[3] / "frontend" / "lib" / "utils" / "splits.ts"
    assert source.exists(), f"garde de parité introuvable : {source}"

    bloc = re.search(r"const SCHEMAS[^=]*=\s*\{(.*?)\n\};", source.read_text("utf-8"), re.S)
    assert bloc, "le bloc SCHEMAS n'a pas la forme attendue dans splits.ts"

    depuis_le_front: dict[str, list[str]] = {}
    for nom, corps in re.findall(r'\n  "?([\w-]+)"?:\s*\[(.*?)\n  \],', bloc.group(1), re.S):
        depuis_le_front[nom] = re.findall(r'key:\s*"([^"]+)"', corps)

    assert depuis_le_front == split_gap.SCHEMAS

def test_the_thresholds_match_the_ones_the_screen_applies():
    """Les quatre seuils existent des deux côtés, et **rien** ne peut les dériver.

    Le produit applique ceux de l'écran ; le script de sondage applique ceux d'ici. Les
    laisser diverger ferait dire « OK » au script pour une règle que le produit n'applique
    plus — exactement le piège que ce lot invoque #76 pour interdire. Le gabarit de
    segments, lui, se **dérive** de `mapping` et n'a pas besoin d'une telle garde ; un
    nombre écrit dans un autre langage, si.
    """
    source = Path(__file__).parents[3] / "frontend" / "components" / "results"
    texte = (source / "RaceFinishers.tsx").read_text("utf-8")
    texte += (source / "ReliabilityMark.tsx").read_text("utf-8")

    def constante(nom: str) -> float:
        trouve = re.search(rf"const {nom} = ([\d.]+);", texte)
        assert trouve, f"constante {nom} introuvable côté écran"
        return float(trouve.group(1))

    assert constante("ECART_SEUIL") == split_gap.OUTLIER_RATIO
    assert constante("ECART_MIN_LIGNES") == split_gap.MIN_EVALUATED_ROWS
    assert constante("ECART_MIN_SECONDES") == split_gap.MIN_GAP_SECONDS
    assert constante("SEUIL_ECART_EPREUVE") == split_gap.EVENT_GAP_RATIO
    assert constante("ECART_MIN_LIGNES_EPREUVE") == split_gap.MIN_EVALUATED_ROWS


def test_a_sport_without_a_predictable_template_is_never_evaluated():
    """`raid-multisport` a un gabarit **vide** — et `all()` sur du vide vaut `True`.

    Sans garde, la somme vaut 0 et chaque ligne rend un écart de 100 % : la page
    annoncerait qu'il manque tout le temps du parcours, sur toutes les lignes.
    """
    assert split_gap.schema_for("raid-multisport") == []
    assert (
        split_gap.ratio(
            _row(splits={"Etape 1": "00:20:00"}, event_type="raid-multisport")
        )
        is None
    )


def test_a_bike_run_is_evaluated_on_its_three_segments():
    """Régression : le gabarit maison omettait `segment1` et inventait un écart de 33 %."""
    row = _row(
        total="01:00:00",
        splits={"segment1": "00:20:00", "bike": "00:25:00", "run": "00:15:00"},
        event_type="bike-run",
    )
    assert split_gap.ratio(row) == pytest.approx(0.0)

"""Tests de l'indice de fiabilité (services/quality.py)."""
from types import SimpleNamespace

from app.services import quality


def _part(status="finisher", total_time="01:59:00", rank_overall=None, is_relay=False):
    return SimpleNamespace(
        status=status, total_time=total_time, rank_overall=rank_overall, is_relay=is_relay
    )


def test_course_saine_est_fiable():
    parts = [_part(rank_overall=1), _part(rank_overall=2), _part(status="DNF", total_time=None)]
    report = quality.analyze(parts)
    assert report.is_reliable is True
    assert report.anomalies == {}


def test_lignes_jetees_pour_doublon_de_dossard():
    report = quality.analyze([_part(rank_overall=1)], duplicate_bibs=2)
    assert report.is_reliable is False
    assert report.anomalies == {quality.ANOMALY_DUPLICATE_BIB: 2}


def test_statut_hors_nomenclature():
    parts = [_part(rank_overall=1), _part(status="DQ", total_time=None), _part(status="Abandon")]
    report = quality.analyze(parts)
    assert report.anomalies[quality.ANOMALY_UNKNOWN_STATUS] == 2
    assert report.is_reliable is False


def test_statut_connu_insensible_a_la_casse():
    report = quality.analyze([_part(status="dnf", total_time=None), _part(status="Dsq")])
    assert quality.ANOMALY_UNKNOWN_STATUS not in report.anomalies


def test_statut_vide_est_indetermine():
    report = quality.analyze([_part(status="", total_time=None)])
    assert report.anomalies[quality.ANOMALY_UNKNOWN_STATUS] == 1


def test_rangs_dupliques():
    parts = [_part(rank_overall=1), _part(rank_overall=1), _part(rank_overall=2)]
    report = quality.analyze(parts)
    assert report.anomalies[quality.ANOMALY_DUPLICATE_RANK] == 1
    # Rangs {1, 1, 2} : max 2, deux rangs distincts → aucun trou.
    assert quality.ANOMALY_RANK_GAP not in report.anomalies


def test_rangs_non_contigus():
    parts = [_part(rank_overall=1), _part(rank_overall=4)]
    report = quality.analyze(parts)
    assert report.anomalies[quality.ANOMALY_RANK_GAP] == 2  # 2 et 3 manquants


def test_solos_et_relais_sont_classes_separement():
    """TimePulse mélange solos et relais : deux « rang 1 » ne sont pas un doublon."""
    parts = [
        _part(rank_overall=1),
        _part(rank_overall=2),
        _part(rank_overall=1, is_relay=True),
        _part(rank_overall=2, is_relay=True),
    ]
    assert quality.analyze(parts).is_reliable is True


def test_seuls_les_finishers_sont_classes():
    """Un DNF sans rang ne creuse pas de trou dans le classement des finishers."""
    parts = [_part(rank_overall=1), _part(status="DNF", total_time=None), _part(rank_overall=2)]
    assert quality.analyze(parts).is_reliable is True


def test_finisher_sans_temps():
    parts = [_part(total_time=None), _part(total_time="00:00:00"), _part(total_time="  ")]
    report = quality.analyze(parts)
    assert report.anomalies[quality.ANOMALY_FINISHER_WITHOUT_TIME] == 3


def test_dnf_sans_temps_est_normal():
    parts = [_part(rank_overall=1), _part(status="DNS", total_time=None)]
    assert quality.analyze(parts).is_reliable is True


def test_course_vide_est_suspecte():
    report = quality.analyze([])
    assert report.is_reliable is False
    assert report.anomalies == {quality.ANOMALY_NO_PARTICIPATION: 1}


def test_anomalies_cumulees():
    parts = [_part(status="DQ", total_time=None), _part(total_time=None, rank_overall=3)]
    report = quality.analyze(parts, duplicate_bibs=1)
    assert report.anomalies == {
        quality.ANOMALY_DUPLICATE_BIB: 1,
        quality.ANOMALY_UNKNOWN_STATUS: 1,
        quality.ANOMALY_FINISHER_WITHOUT_TIME: 1,
        quality.ANOMALY_RANK_GAP: 2,
    }


# --- #909 : aucun finisher, temps de finisher invalide, non-finisher classé ---


def test_une_course_100_pourcent_dnf_classes_est_signalee():
    parts = [_part(status="DNF", total_time=None, rank_overall=rang) for rang in (1, 2, 3)]
    report = quality.analyze(parts)
    assert report.is_reliable is False
    assert report.anomalies[quality.ANOMALY_NO_FINISHER] == 1
    assert report.anomalies[quality.ANOMALY_NON_FINISHER_WITH_RESULT] == 3


def test_une_course_sans_aucun_finisher_ni_resultat_est_signalee():
    report = quality.analyze([_part(status="DNS", total_time=None)])
    assert report.anomalies == {quality.ANOMALY_NO_FINISHER: 1}


def test_un_temps_de_finisher_non_interpretable_est_signale():
    parts = [
        _part(rank_overall=1),
        _part(rank_overall=2, total_time="Abandon"),
        _part(rank_overall=3, total_time="-00:00:06"),
    ]
    report = quality.analyze(parts)
    assert report.anomalies == {quality.ANOMALY_INVALID_FINISHER_TIME: 2}


def test_les_formats_de_temps_legitimes_ne_sont_pas_signales():
    parts = [
        _part(rank_overall=1, total_time="00:13:39 (00:13:39)"),
        _part(rank_overall=2, total_time="00:33'41\"000"),
        _part(rank_overall=3, total_time="39:11"),
    ]
    assert quality.analyze(parts).anomalies == {}


def test_un_temps_nul_reste_un_finisher_sans_temps_et_pas_un_temps_invalide():
    report = quality.analyze([_part(rank_overall=1, total_time="00:00:00")])
    assert report.anomalies == {quality.ANOMALY_FINISHER_WITHOUT_TIME: 1}


def test_un_dns_classe_et_chronometre_est_signale():
    parts = [
        _part(rank_overall=1),
        _part(status="DNS", total_time="03:27:00", rank_overall=66),
        _part(status="DSQ", total_time="00:00:00", rank_overall=None),
    ]
    report = quality.analyze(parts)
    assert report.anomalies == {quality.ANOMALY_NON_FINISHER_WITH_RESULT: 1}

"""Doublons suspects : ce que le seuil large attrape, et ce qu'il refuse (#288).

Les trois cas connus sont reconstitués avec les **valeurs mesurées** du sondage
`docs/superpowers/specs/2026-08-12-sources-multiples-epreuve-sondage.md` et du
commentaire de terrain de la discussion #210 (Mesquer `id=38` / `id=50`) — pas
inventées : c'est le seul moyen que le seuil soit réglé sur la réalité et non sur
l'idée qu'on s'en fait.

**Les deux tests de faux positifs (AC2, AC3) sont ceux qui cadrent le seuil.**
Sans eux, une détection qui rendrait *tout* satisferait l'AC1 : ce sont les
éditions successives et les heats d'un même événement qui rendent le réglage
falsifiable. Le sondage les a mesurés — le nom seul rapproche 37 paires sur 4 465
dans la base de dev, dont 20 sont des heats du même événement, et aucune n'est un
vrai doublon.
"""
from datetime import date

import pytest

from app.core import sql_observability
from app.models.athlete import Athlete
from app.models.participation import Participation
from app.repositories import course_repository
from app.services import course_duplicates

# --- Les URLs réelles des trois cas connus -----------------------------------

#: Mesquer, l'URL Breizh Chrono du seul heat `triathlon-s-indiv` — celle que
#: `id=38` et `id=50` partagent **à l'octet près** en preview (#210).
MESQUER_BREIZH = (
    "https://resultats.breizhchrono.com/resultats-courses/"
    "triathlon-et-swimrun-mesquer-quimiac-2026-1677015306084-12/triathlon-s-indiv"
)
MESQUER_KLIKEGO_S = (
    "https://www.klikego.com/resultats/triathlon-et-swimrun-mesquer-quimiac-2026/"
    "1677015306084-12?heat=triathlon-s-indiv"
)
MESQUER_KLIKEGO_XS = (
    "https://www.klikego.com/resultats/triathlon-et-swimrun-mesquer-quimiac-2026/"
    "1677015306084-12?heat=triathlon-xs-indiv"
)
#: Nozéen 2026 : le même identifiant de plateforme `1517534975128-8` chez les deux
#: chronométreurs, et deux façades qui ne nomment pas la même chose (sondage Q4).
NOZEEN_2026_KLIKEGO = (
    "https://www.klikego.com/resultats/6e-duathlon-nozeen-2026/"
    "1517534975128-8?heat=duathlon-s---open"
)
NOZEEN_2026_BREIZH = (
    "https://live.breizhchrono.com/external/live5/classements.jsp"
    "?version=new&reference=1517534975128-8&heat=duathlon-s---open"
)
#: L'édition précédente. Le suffixe `-7` au lieu de `-8` : c'est **lui** qui
#: distingue l'édition, jamais le préfixe (sondage Q2).
NOZEEN_2025_KLIKEGO = (
    "https://www.klikego.com/resultats/5e-duathlon-nozeen-2025/"
    "1517534975128-7?heat=duathlon-s---open"
)
#: Vertou : deux des quatre formes d'URL du Sheet. Aucun identifiant de
#: plateforme — wiclax est le seul des 14 fournisseurs à n'en porter aucun.
VERTOU_WICLAX = (
    "https://www.chronosmetron.wiclax-results.com/Triathlon%20de%20Vertou%202026/"
    "?parcours=s-open"
)
VERTOU_CHRONOSMETRON = (
    "https://www.chronosmetron.com/754-triathlon-de-vertou-2026?parcours=s-open"
)
#: Dinard via la **seule** façade `live.` : 6 swimruns, un identifiant, un host.
DINARD_LIVE = (
    "https://live.breizhchrono.com/external/live5/classements.jsp"
    "?version=new&reference=1488071608761-688&heat="
)


def _epreuve(
    db_session,
    *,
    name: str,
    event_date: date | None,
    event_type: str,
    url: str,
    provider: str,
    is_relay: bool = False,
    participations: int = 0,
    tcn: int = 0,
):
    """Une épreuve, sa source active, et `participations` résultats dont `tcn` du club."""
    course = course_repository.get_or_create(
        db_session,
        name=name,
        event_date=event_date,
        event_type=event_type,
        is_relay=is_relay,
        source_url=url,
        provider=provider,
    )
    for numero in range(participations):
        athlete = Athlete(nom=f"NOM-{course.id}-{numero}", prenom="Prénom")
        db_session.add(athlete)
        db_session.flush()
        db_session.add(
            Participation(
                course_id=course.id,
                athlete_id=athlete.id,
                bib_number=str(numero),
                club="Triathlon Club Nantais" if numero < tcn else "Autre Club",
            )
        )
    db_session.flush()
    return course


def _motifs_par_paire(candidats) -> dict[tuple[int, int], str]:
    return {
        (candidat["courses"][0]["id"], candidat["courses"][1]["id"]): candidat["reason"]
        for candidat in candidats
    }


@pytest.fixture
def compteur_sql(db_session):
    """Arme le bilan agrégé de `core/sql_observability` sur l'engine du test.

    `_stats_enabled` est un état de **module** : sans le `reset_for_tests` des
    deux côtés, un test armé contaminerait les suivants.
    """
    sql_observability.reset_for_tests()
    sql_observability.install(db_session.get_bind(), slow_query_ms=0, collect_stats=True)
    yield
    sql_observability.reset_for_tests()


def test_les_trois_cas_connus_ressortent_tous(db_session):
    """AC1 — Mesquer, Nozéen et Vertou, chacun par le motif qui lui correspond.

    Les trois ont été trouvés **à l'œil**, par hasard, sur une fiche coureur.
    C'est cette découverte fortuite que l'écran remplace, et les trois motifs
    n'en font pas trop : chacun est le seul à attraper son cas.
    """
    mesquer_swimrun = _epreuve(
        db_session,
        name="Triathlon et SwimRun Mesquer-Quimiac 2026",
        event_date=date(2026, 6, 13),
        event_type="swimrun-s",
        url=MESQUER_BREIZH,
        provider="breizhchrono",
        participations=4,
        tcn=2,
    )
    mesquer_triathlon = _epreuve(
        db_session,
        name="Triathlon et SwimRun Mesquer-Quimiac 2026",
        event_date=date(2026, 6, 13),
        event_type="triathlon-s",
        url=MESQUER_BREIZH,
        provider="breizhchrono",
        participations=4,
        tcn=1,
    )
    nozeen_klikego = _epreuve(
        db_session,
        name="6e Duathlon Nozéen 2026",
        event_date=date(2026, 4, 12),
        event_type="duathlon-s",
        url=NOZEEN_2026_KLIKEGO,
        provider="klikego",
        participations=3,
    )
    nozeen_breizh = _epreuve(
        db_session,
        name="Duathlon Nozéen - Duathlon S Open",
        event_date=date(2026, 4, 12),
        event_type="duathlon-s",
        url=NOZEEN_2026_BREIZH,
        provider="breizhchrono",
        participations=3,
    )
    vertou_wiclax = _epreuve(
        db_session,
        name="Triathlon de Vertou - S-Open",
        event_date=date(2026, 5, 3),
        event_type="triathlon-s",
        url=VERTOU_WICLAX,
        provider="wiclax",
        participations=2,
    )
    vertou_chronosmetron = _epreuve(
        db_session,
        name="Triathlon de Vertou 2026 - S-Open",
        event_date=date(2026, 5, 3),
        event_type="triathlon-s",
        url=VERTOU_CHRONOSMETRON,
        provider="wiclax",
        participations=2,
    )

    motifs = _motifs_par_paire(course_duplicates.find_candidates(db_session))

    assert motifs == {
        (mesquer_swimrun.id, mesquer_triathlon.id): "same_source_url",
        (nozeen_klikego.id, nozeen_breizh.id): "shared_event_id",
        (vertou_wiclax.id, vertou_chronosmetron.id): "close_names",
    }


def test_deux_editions_successives_ne_sont_pas_un_doublon(db_session):
    """AC2 — Nozéen 2025 et 2026, que le nom seul rapprocherait.

    Les deux normalisations utiles au cas Vertou — l'ordinal d'édition de tête
    (`5e`, `6e`) et le millésime — effacent **exactement** ce qui distingue deux
    éditions : `5e Duathlon Nozéen 2025` et `6e Duathlon Nozéen 2026` se
    ramènent tous deux à `duathlon nozeen`. Ce qui les sépare est donc ailleurs,
    et à deux endroits mesurés : la date (364 jours) et le suffixe d'édition de
    l'identifiant de plateforme (`-7` contre `-8`).
    """
    _epreuve(
        db_session,
        name="5e Duathlon Nozéen 2025",
        event_date=date(2025, 4, 13),
        event_type="duathlon-s",
        url=NOZEEN_2025_KLIKEGO,
        provider="klikego",
        participations=3,
    )
    _epreuve(
        db_session,
        name="6e Duathlon Nozéen 2026",
        event_date=date(2026, 4, 12),
        event_type="duathlon-s",
        url=NOZEEN_2026_KLIKEGO,
        provider="klikego",
        participations=3,
    )

    assert course_duplicates.find_candidates(db_session) == []


def test_deux_heats_du_meme_evenement_ne_sont_pas_un_doublon(db_session):
    """AC3 — les heats de Mesquer partagent nom, date, URL d'événement et identifiant.

    `triathlon-s` et `triathlon-xs` sont deux épreuves réellement distinctes, et
    tout ce qui les rapprocherait est vrai : même nom d'événement, même jour,
    même identifiant de plateforme. Seul `event_type` les sépare — d'où sa
    présence dans **chacun** des trois motifs.
    """
    _epreuve(
        db_session,
        name="Triathlon et SwimRun Mesquer-Quimiac 2026",
        event_date=date(2026, 6, 13),
        event_type="triathlon-s",
        url=MESQUER_KLIKEGO_S,
        provider="klikego",
        participations=3,
    )
    _epreuve(
        db_session,
        name="Triathlon et SwimRun Mesquer-Quimiac 2026",
        event_date=date(2026, 6, 13),
        event_type="triathlon-xs",
        url=MESQUER_KLIKEGO_XS,
        provider="klikego",
        participations=3,
    )

    assert course_duplicates.find_candidates(db_session) == []


def test_deux_heats_de_meme_type_sur_une_seule_facade_ne_sont_pas_un_doublon(db_session):
    """AC3, le cas coûteux — les 6 swimruns de Dinard, mesurés.

    Ils partagent l'identifiant `1488071608761-688`, l'`event_type` `swimrun`
    **et** `is_relay=False` (les « duo » ne sont pas détectés comme relais,
    #295) : seul leur nom diffère. Un motif « identifiant partagé » sans garde
    de façade en sortait **15 paires** sur la base de dev, toutes fausses.

    Le garde est le host, et sa raison n'est pas statistique : deux lignes issues
    de la **même** façade sont une seule publication de l'événement, donc des
    heats distincts. Deux publications, ce sont deux façades — c'est là, et là
    seulement, que le nom et la date ont le droit de diverger.
    """
    for heat, nom in (
        ("swimrun-court-solo", "Swimrun Court Solo"),
        ("swimrun-court-duo", "Swimrun Court Duo"),
        ("swimrun-medium-solo", "Swimrun Medium ZOGGS Solo"),
    ):
        _epreuve(
            db_session,
            name=f"Triathlon SwimRun Dinard Côte d'Emeraude - {nom}",
            event_date=date(2025, 9, 14),
            event_type="swimrun",
            url=f"{DINARD_LIVE}{heat}",
            provider="breizhchrono",
            participations=2,
        )

    assert course_duplicates.find_candidates(db_session) == []


def test_une_url_d_evenement_portant_n_heats_n_est_pas_un_doublon(db_session):
    """Le pendant du motif « même URL » — mesuré, lui aussi.

    TimePulse publie ses six heats sous **une** URL d'événement et sous le
    **même nom** ; seuls `event_type` et `is_relay` les distinguent. Rapprocher
    sur l'égalité d'URL seule en sortait 16 paires sur la base de dev.

    Ce qui rend Mesquer suspect n'est donc pas de partager une URL, c'est de
    partager une URL qui **désigne un seul heat** : elle ne peut pas porter deux
    épreuves, donc les deux lignes sont deux passes de la même page.
    """
    url_evenement = "https://www.timepulse.fr/epreuves/resultats/live/3232"
    for event_type, is_relay in (
        ("triathlon-l", False),
        ("triathlon-l", True),
        ("triathlon-m", False),
    ):
        _epreuve(
            db_session,
            name="LE NORTH MAY",
            event_date=date(2026, 6, 7),
            event_type=event_type,
            is_relay=is_relay,
            url=url_evenement,
            provider="timepulse",
            participations=2,
        )

    assert course_duplicates.find_candidates(db_session) == []


def test_chaque_paire_porte_de_quoi_trancher_sans_seconde_requete(db_session):
    """Les huit champs de l'issue, et les compteurs séparés club / total.

    « Le nombre d'athlètes est différent entre les 2 imports » est l'observation
    d'origine de #261 : c'est **l'écart** entre les deux compteurs qui dit
    laquelle des deux lignes garder, il doit donc être lisible sur la paire.
    """
    gauche = _epreuve(
        db_session,
        name="Triathlon de Vertou - S-Open",
        event_date=date(2026, 5, 3),
        event_type="triathlon-s",
        url=VERTOU_WICLAX,
        provider="wiclax",
        participations=5,
        tcn=3,
    )
    droite = _epreuve(
        db_session,
        name="Triathlon de Vertou 2026 - S-Open",
        event_date=date(2026, 5, 3),
        event_type="triathlon-s",
        url=VERTOU_CHRONOSMETRON,
        provider="wiclax",
        participations=2,
        tcn=1,
    )

    (candidat,) = course_duplicates.find_candidates(db_session)

    assert candidat["courses"][0] == {
        "id": gauche.id,
        "name": "Triathlon de Vertou - S-Open",
        "event_date": date(2026, 5, 3),
        "event_type": "triathlon-s",
        "is_relay": False,
        "provider": "wiclax",
        "source_url": VERTOU_WICLAX,
        "total": 5,
        "tcn_count": 3,
    }
    assert candidat["courses"][1]["id"] == droite.id
    assert (candidat["courses"][1]["total"], candidat["courses"][1]["tcn_count"]) == (2, 1)


def test_une_paire_ne_sort_qu_une_fois_sous_son_motif_le_plus_precis(db_session):
    """Deux motifs sur la même paire ne font pas deux lignes à examiner.

    Nozéen sous ses deux façades partage l'identifiant **et**, si le nom Breizh
    Chrono se trouve porter le millésime, se rapproche aussi par les noms. La
    paire sort une fois, sous le motif le plus **spécifique** — l'identifiant,
    qui vient du chronométreur, plutôt qu'une ressemblance de libellé.
    """
    gauche = _epreuve(
        db_session,
        name="6e Duathlon Nozéen 2026",
        event_date=date(2026, 4, 12),
        event_type="duathlon-s",
        url=NOZEEN_2026_KLIKEGO,
        provider="klikego",
        participations=2,
    )
    droite = _epreuve(
        db_session,
        name="Duathlon Nozéen",
        event_date=date(2026, 4, 12),
        event_type="duathlon-s",
        url=NOZEEN_2026_BREIZH,
        provider="breizhchrono",
        participations=2,
    )

    assert _motifs_par_paire(course_duplicates.find_candidates(db_session)) == {
        (gauche.id, droite.id): "shared_event_id"
    }


def test_la_detection_tient_en_une_requete_quel_que_soit_le_nombre_d_epreuves(
    db_session, compteur_sql
):
    """AC5 — une requête agrégée, et **aucun** N+1 sur les participations.

    Le compteur SQL est le seul filet qui le prouve : lire
    `course.participations` par épreuve donnerait la même réponse, en une requête
    par ligne — invisible en test fonctionnel, et c'est justement le défaut que
    `core/sql_observability` existe pour rendre visible (« 1812 requêtes pour
    1810 participants »).
    """
    for numero in range(2):
        _epreuve(
            db_session,
            name=f"Épreuve {numero}",
            event_date=date(2026, 5, 3),
            event_type="triathlon-s",
            url=f"https://www.klikego.com/resultats/epreuve-{numero}/17000000000{numero}-1",
            provider="klikego",
            participations=3,
            tcn=1,
        )
    with sql_observability.measure_queries("deux épreuves") as deux:
        course_duplicates.find_candidates(db_session)

    for numero in range(2, 10):
        _epreuve(
            db_session,
            name=f"Épreuve {numero}",
            event_date=date(2026, 5, 3),
            event_type="triathlon-s",
            url=f"https://www.klikego.com/resultats/epreuve-{numero}/17000000000{numero}-1",
            provider="klikego",
            participations=3,
            tcn=1,
        )
    with sql_observability.measure_queries("dix épreuves") as dix:
        course_duplicates.find_candidates(db_session)

    assert deux.count == 1
    assert dix.count == 1

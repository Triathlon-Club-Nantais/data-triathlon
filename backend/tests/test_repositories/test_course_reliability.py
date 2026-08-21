"""`Course.is_reliable` : deux colonnes, une propriété (#115, FR-037 à FR-039).

Les deux colonnes évoluent **indépendamment** — ce ne sont pas deux états d'une
machine, ce sont deux faits qui coexistent : ce que la machine constate, et ce
qu'un humain a tranché.
"""
from datetime import date

import pytest

from app.models.course import Course
from app.repositories import course_repository


def _epreuve(db_session, **colonnes) -> Course:
    course = Course(name=colonnes.pop("name", "Épreuve"), **colonnes)
    db_session.add(course)
    db_session.flush()
    return course


def test_l_avis_humain_prime_sur_le_verdict_calcule(db_session):
    course = _epreuve(db_session, is_reliable_computed=False, reliability_override=True)

    assert course.is_reliable is True


def test_sans_avis_humain_le_verdict_calcule_fait_foi(db_session):
    course = _epreuve(db_session, is_reliable_computed=False, reliability_override=None)

    assert course.is_reliable is False


def test_sans_rien_le_verdict_est_indetermine(db_session):
    """`NULL` = jamais évaluée, et surtout pas « douteuse ».

    Un `false` par défaut déclarerait suspectes toutes les épreuves antérieures
    à l'indice ; un `true` les blanchirait sans preuve.
    """
    course = _epreuve(db_session)

    assert course.is_reliable is None


@pytest.mark.parametrize(
    ("calcule", "humain", "attendu"),
    [
        (True, None, True),
        (False, None, False),
        (True, False, False),
        (False, True, True),
        (None, True, True),
        (None, None, None),
    ],
)
def test_la_table_de_verite_complete(db_session, calcule, humain, attendu):
    course = _epreuve(
        db_session, is_reliable_computed=calcule, reliability_override=humain
    )

    assert course.is_reliable is attendu


def test_la_propriete_est_utilisable_dans_un_where(db_session):
    """Sans son `@expression`, elle serait **illisible en SQL**.

    C'est la moitié qu'on oublie : la propriété Python marcherait, et le premier
    filtre `WHERE Course.is_reliable` lèverait — ou pire, filtrerait sur autre
    chose.
    """
    _epreuve(db_session, name="Fiable calculée", is_reliable_computed=True)
    _epreuve(
        db_session,
        name="Douteuse blanchie",
        is_reliable_computed=False,
        reliability_override=True,
    )
    _epreuve(
        db_session,
        name="Fiable déclassée",
        is_reliable_computed=True,
        reliability_override=False,
    )

    fiables = (
        db_session.query(Course).filter(Course.is_reliable.is_(True)).all()
    )

    assert {course.name for course in fiables} == {"Fiable calculée", "Douteuse blanchie"}


def test_lever_l_avis_humain_fait_reapparaitre_le_dernier_verdict_calcule(db_session):
    """FR-039 — le **dernier**, pas celui qui valait au moment de la décision.

    C'est ce que `coalesce` achète et qu'une colonne unique aurait perdu : entre
    la décision humaine et sa levée, l'import a continué d'écrire sa colonne.
    """
    course = _epreuve(db_session, is_reliable_computed=False)
    course.reliability_override = True
    db_session.flush()

    # L'import repasse pendant ce temps et redresse son verdict.
    course_repository.set_quality(
        db_session, course, is_reliable_computed=True, quality_issues={}
    )
    db_session.flush()
    assert course.is_reliable is True, "l'avis humain reste le même, il dit déjà vrai"

    course.reliability_override = None
    db_session.flush()

    assert course.is_reliable is True
    assert course.is_reliable_computed is True


def test_l_import_n_ecrase_jamais_l_avis_humain(db_session):
    """FR-037 — les deux chemins d'écriture ne se croisent pas.

    Aucune garde applicative ne le tient : `set_quality` écrit sa colonne,
    toujours et sans condition. C'est la **forme** qui l'assure.
    """
    course = _epreuve(db_session, is_reliable_computed=True, reliability_override=False)

    course_repository.set_quality(
        db_session, course, is_reliable_computed=True, quality_issues={"rank_gap": 3}
    )
    db_session.flush()

    assert course.reliability_override is False
    assert course.is_reliable is False, "l'humain a tranché, l'import ne le défait pas"
    assert course.quality_issues == {"rank_gap": 3}


def _epreuve_filtrable(db_session, **colonnes):
    """Une épreuve nommée et datée, pour que le tri du catalogue ait prise."""
    course = Course(
        name=colonnes.pop("name", "Épreuve"),
        event_type="triathlon-m",
        event_date=colonnes.pop("event_date", date(2026, 6, 1)),
        **colonnes,
    )
    db_session.add(course)
    db_session.flush()
    return course


def test_le_filtre_unreliable_ne_garde_que_les_epreuves_douteuses(db_session):
    douteuse = _epreuve_filtrable(db_session, name="Douteuse", is_reliable_computed=False)
    _epreuve_filtrable(db_session, name="Fiable", is_reliable_computed=True)

    resultats = course_repository.list_all(db_session, unreliable=True)

    assert [c.id for c in resultats] == [douteuse.id]


def test_une_epreuve_jamais_evaluee_reste_hors_de_la_file(db_session):
    """`NULL` n'est pas « douteuse » : c'est « jamais évaluée ».

    L'y inclure ferait tomber dans la file toute la base antérieure à l'indice.
    """
    _epreuve_filtrable(db_session, name="Jamais évaluée", is_reliable_computed=None)

    assert course_repository.list_all(db_session, unreliable=True) == []


def test_l_avis_humain_favorable_sort_l_epreuve_de_la_file(db_session):
    """Le `coalesce` fait tout le travail : l'avis humain prime sur le calculé."""
    _epreuve_filtrable(
        db_session, name="Revalidée", is_reliable_computed=False, reliability_override=True
    )

    assert course_repository.list_all(db_session, unreliable=True) == []


def test_l_avis_humain_defavorable_fait_entrer_l_epreuve_dans_la_file(db_session):
    """Une épreuve que la machine juge saine mais qu'un humain conteste est du
    travail en attente, donc dans la file."""
    contestee = _epreuve_filtrable(
        db_session, name="Contestée", is_reliable_computed=True, reliability_override=False
    )

    resultats = course_repository.list_all(db_session, unreliable=True)

    assert [c.id for c in resultats] == [contestee.id]


def test_sans_le_filtre_le_catalogue_est_inchange(db_session):
    """Le paramètre est additif : son absence ne change aucune réponse."""
    _epreuve_filtrable(db_session, name="Douteuse", is_reliable_computed=False)
    _epreuve_filtrable(db_session, name="Fiable", is_reliable_computed=True)
    _epreuve_filtrable(db_session, name="Jamais évaluée", is_reliable_computed=None)

    assert len(course_repository.list_all(db_session)) == 3


def test_count_all_compte_le_meme_ensemble_que_list_all(db_session):
    """Sinon la pagination annoncerait une page 4 qui ne rend rien."""
    _epreuve_filtrable(db_session, name="Douteuse 1", is_reliable_computed=False)
    _epreuve_filtrable(db_session, name="Douteuse 2", is_reliable_computed=False)
    _epreuve_filtrable(db_session, name="Fiable", is_reliable_computed=True)

    assert course_repository.count_all(db_session, unreliable=True) == 2
    assert len(course_repository.list_all(db_session, unreliable=True)) == 2


def test_le_filtre_unreliable_se_combine_aux_filtres_du_catalogue(db_session):
    """Les filtres se composent — la file reste filtrable par nom et par date."""
    cible = _epreuve_filtrable(
        db_session, name="Triathlon de Vertou", is_reliable_computed=False
    )
    _epreuve_filtrable(db_session, name="Triathlon de Carnac", is_reliable_computed=False)

    resultats = course_repository.list_all(db_session, unreliable=True, name="Vertou")

    assert [c.id for c in resultats] == [cible.id]

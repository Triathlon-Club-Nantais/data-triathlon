"""`Course.is_reliable` : deux colonnes, une propriété (#115, FR-037 à FR-039).

Les deux colonnes évoluent **indépendamment** — ce ne sont pas deux états d'une
machine, ce sont deux faits qui coexistent : ce que la machine constate, et ce
qu'un humain a tranché.
"""
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

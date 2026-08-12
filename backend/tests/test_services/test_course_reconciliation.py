"""Extraction `(platform_event_id, heat_slug)` et recherche de rapprochement (#289).

Règle R du sondage #277 : deux `Course` sont la même épreuve si et seulement si
provider ∈ {klikego, breizhchrono} des deux côtés, et si les deux identifiants
sont non vides et égaux. Ce fichier teste l'extraction et la recherche isolées
de l'import ; le scénario de bout en bout (deux façades Breizh Chrono, une
seule `Course`) vit dans `test_platform_event_reconciliation.py`.
"""
from datetime import date

from app.models.course import Course
from app.models.course_source import CourseSource
from app.services.course_reconciliation import (
    find_reconcilable_course,
    heat_slug,
    platform_event_id,
)

KLIKEGO_URL = "https://www.klikego.com/resultats/mesquer-2026/1706667557931-4?heat=triathlon-s-indiv"
BC_RESULTATS_URL = (
    "https://resultats.breizhchrono.com/resultats-courses/"
    "dinard-1488071608761-688/swimrun-court-duo"
)
BC_COUREUR_URL = (
    "https://resultats.breizhchrono.com/bc/resultats/coureur.jsp"
    "?ref=1488071608761-688&heat=swimrun-court-duo&dossard=42"
)
BC_LIVE_URL = (
    "https://live.breizhchrono.com/external/live5/classements.jsp"
    "?version=new&reference=1488071608761-688&heat=swimrun-court-duo"
)


class TestPlatformEventId:
    def test_klikego_dernier_segment_de_path(self):
        assert platform_event_id("klikego", KLIKEGO_URL) == "1706667557931-4"

    def test_breizhchrono_resultats_suffixe_numerique_du_slug(self):
        assert platform_event_id("breizhchrono", BC_RESULTATS_URL) == "1488071608761-688"

    def test_breizhchrono_coureur_jsp_query_ref(self):
        assert platform_event_id("breizhchrono", BC_COUREUR_URL) == "1488071608761-688"

    def test_breizhchrono_live_query_reference(self):
        assert platform_event_id("breizhchrono", BC_LIVE_URL) == "1488071608761-688"

    def test_fournisseur_non_reconciliable_rend_vide(self):
        assert platform_event_id("wiclax", "https://chronosmetron.wiclax-results.com/Vertou/") == ""

    def test_url_illisible_rend_vide_plutot_que_de_lever(self):
        assert platform_event_id("breizhchrono", "pas-une-url") == ""

    def test_ne_tronque_jamais_au_prefixe_epoch(self):
        """12 préfixes sur 40 mesurés dans le Sheet du club portent plusieurs
        éditions ; tronquer à `1488071608761` confondrait Dinard avec les 7
        autres événements qui partagent ce compte de plateforme."""
        assert platform_event_id("breizhchrono", BC_RESULTATS_URL) != "1488071608761"


class TestHeatSlug:
    def test_klikego_query_heat(self):
        assert heat_slug("klikego", KLIKEGO_URL) == "triathlon-s-indiv"

    def test_breizhchrono_resultats_troisieme_segment(self):
        assert heat_slug("breizhchrono", BC_RESULTATS_URL) == "swimrun-court-duo"

    def test_breizhchrono_live_query_heat(self):
        assert heat_slug("breizhchrono", BC_LIVE_URL) == "swimrun-court-duo"

    def test_mis_en_minuscules(self):
        url = "https://www.klikego.com/resultats/x/1-1?heat=Duathlon-S---OPEN"
        assert heat_slug("klikego", url) == "duathlon-s---open"

    def test_ne_normalise_rien_dautre_que_la_casse(self):
        """Le triple tiret est porteur de sens (`_detect_relay`) : deux heats
        qui ne diffèrent que par lui restent deux heats différents."""
        solo = heat_slug("klikego", "https://www.klikego.com/resultats/x/1-1?heat=duathlon-s---open")
        relais = heat_slug("klikego", "https://www.klikego.com/resultats/x/1-1?heat=duathlon-s---en-relais")
        assert solo != relais


class TestFindReconcilableCourse:
    def _course_avec_source(self, db_session, *, url: str, provider: str) -> Course:
        course = Course(
            name="Nom quelconque", event_date=date(2025, 1, 1),
            event_type="triathlon-s", is_relay=False,
        )
        db_session.add(course)
        db_session.flush()
        db_session.add(CourseSource(course_id=course.id, url=url, provider=provider, is_active=True))
        db_session.flush()
        return course

    def test_rapproche_les_deux_facades_breizhchrono_malgre_un_nom_different(self, db_session):
        cible = self._course_avec_source(db_session, url=BC_RESULTATS_URL, provider="breizhchrono")

        trouve = find_reconcilable_course(db_session, provider="breizhchrono", source_url=BC_LIVE_URL)

        assert trouve is not None
        assert trouve.id == cible.id

    def test_ne_rapproche_pas_un_heat_different(self, db_session):
        self._course_avec_source(db_session, url=BC_RESULTATS_URL, provider="breizhchrono")
        autre_heat = BC_LIVE_URL.replace("swimrun-court-duo", "swimrun-court-solo")

        assert find_reconcilable_course(db_session, provider="breizhchrono", source_url=autre_heat) is None

    def test_ne_rapproche_pas_un_evenement_different(self, db_session):
        self._course_avec_source(db_session, url=BC_RESULTATS_URL, provider="breizhchrono")
        autre_event = BC_LIVE_URL.replace("1488071608761-688", "1488071608761-999")

        assert find_reconcilable_course(db_session, provider="breizhchrono", source_url=autre_event) is None

    def test_ne_regarde_jamais_un_fournisseur_hors_klikego_breizhchrono(self, db_session):
        self._course_avec_source(db_session, url=BC_RESULTATS_URL, provider="breizhchrono")

        assert find_reconcilable_course(db_session, provider="wiclax", source_url=BC_LIVE_URL) is None

    def test_url_vide_ne_rapproche_rien(self, db_session):
        self._course_avec_source(db_session, url=BC_RESULTATS_URL, provider="breizhchrono")

        assert find_reconcilable_course(db_session, provider="breizhchrono", source_url="") is None

    def test_aucune_source_en_base_ne_rapproche_rien(self, db_session):
        assert find_reconcilable_course(db_session, provider="breizhchrono", source_url=BC_LIVE_URL) is None

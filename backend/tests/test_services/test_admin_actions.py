"""Les gestes correctifs d'un administrateur (#117).

Le fil de tous ces tests : **un refus ne laisse aucune trace, ni en base ni au
journal** (FR-015), et **une demande sans effet n'est pas un geste** (FR-012).
"""
import time
from datetime import date

import pytest

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.scrapers.base import ScrapedResult
from app.services import admin_actions, import_service


@pytest.fixture
def auteur(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    return user


def _epreuve(db_session, nom="Triathlon de Nantes", event_date=date(2026, 5, 17)):
    course = course_repository.get_or_create(
        db_session,
        name=nom,
        event_date=event_date,
        event_type="triathlon-m",
        source_url=f"https://k/{nom}",
        provider="klikego",
    )
    db_session.flush()
    return course


def _coureur(db_session, nom, prenom="Coureur", birth_date=None):
    athlete = athlete_repository.get_or_create(
        db_session, nom=nom, prenom=prenom, birth_date=birth_date
    )
    db_session.flush()
    return athlete


def _inscrit(db_session, athlete, course, dossard="1"):
    ligne = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=dossard
    )
    db_session.flush()
    return ligne


def _journal(db_session, entity_type, entity_id):
    return admin_action_log_repository.list_for_entity(
        db_session, entity_type=entity_type, entity_id=entity_id
    )


# --- Supprimer une épreuve (US1) --------------------------------------------


def test_delete_course_emporte_ses_resultats(db_session, auteur):
    course = _epreuve(db_session)
    _inscrit(db_session, _coureur(db_session, "UN"), course, "1")
    _inscrit(db_session, _coureur(db_session, "DEUX"), course, "2")
    course_id = course.id

    admin_actions.delete_course(db_session, course_id=course_id, user_id=auteur.id)

    assert course_repository.get(db_session, course_id) is None
    assert participation_repository.count_for_course(db_session, course_id) == 0


def test_delete_course_purge_les_fiches_devenues_vides(db_session, auteur):
    """FR-022 — mais **seulement** celles qui perdent leur dernier résultat."""
    cible = _epreuve(db_session, "Cible")
    autre = _epreuve(db_session, "Autre", date(2026, 6, 1))
    exclusif = _coureur(db_session, "EXCLUSIF")
    partage = _coureur(db_session, "PARTAGE")
    _inscrit(db_session, exclusif, cible, "1")
    _inscrit(db_session, partage, cible, "2")
    _inscrit(db_session, partage, autre, "2")

    admin_actions.delete_course(db_session, course_id=cible.id, user_id=auteur.id)

    assert athlete_repository.get(db_session, exclusif.id) is None
    assert athlete_repository.get(db_session, partage.id) is not None


def test_delete_course_consigne_le_geste(db_session, auteur):
    """FR-013 — la trace nomme l'épreuve : un identifiant mort ne désigne rien."""
    course = _epreuve(db_session)
    exclusif = _coureur(db_session, "EXCLUSIF")
    _inscrit(db_session, exclusif, course, "1")
    course_id, exclusif_id = course.id, exclusif.id

    admin_actions.delete_course(db_session, course_id=course_id, user_id=auteur.id)

    entrees = _journal(db_session, "course", course_id)
    assert len(entrees) == 1
    entree = entrees[0]
    assert entree.action == "course.delete"
    assert entree.user_id == auteur.id
    assert entree.payload["name"] == "Triathlon de Nantes"
    assert entree.payload["participations_deleted"] == 1
    assert entree.payload["athletes_purged"] == [exclusif_id]


def test_delete_course_sur_epreuve_inexistante_refuse_et_n_ecrit_rien(db_session, auteur):
    from app.models.admin_action_log import AdminActionLog

    with pytest.raises(NotFoundError):
        admin_actions.delete_course(db_session, course_id=4242, user_id=auteur.id)

    assert db_session.query(AdminActionLog).count() == 0


def test_delete_course_n_emporte_aucun_orphelin_preexistant(db_session, auteur):
    """Le geste reste dans son périmètre : il ne fait pas le ménage de la base.

    Un orphelin antérieur, sans rapport avec l'épreuve, doit survivre — sinon la
    trace du geste devient fausse et la suppression déborde de ce qu'elle annonce.
    """
    course = _epreuve(db_session)
    _inscrit(db_session, _coureur(db_session, "INSCRIT"), course, "1")
    orphelin_anterieur = _coureur(db_session, "ORPHELIN-ANTERIEUR")

    admin_actions.delete_course(db_session, course_id=course.id, user_id=auteur.id)

    assert athlete_repository.get(db_session, orphelin_anterieur.id) is not None


# --- L'ampleur annoncée est l'ampleur réelle (SC-007) ------------------------


def test_l_impact_annonce_est_exactement_ce_qui_est_supprime(db_session, auteur):
    """SC-007 — le test qui empêche les deux définitions de diverger.

    L'impact et la purge doivent venir de la même fonction de repository. S'ils
    divergent, la modale de confirmation ment sur un geste sans retour arrière.
    """
    cible = _epreuve(db_session, "Cible")
    autre = _epreuve(db_session, "Autre", date(2026, 6, 1))
    for indice in range(3):
        _inscrit(db_session, _coureur(db_session, f"EXCLUSIF{indice}"), cible, str(indice))
    partage = _coureur(db_session, "PARTAGE")
    _inscrit(db_session, partage, cible, "9")
    _inscrit(db_session, partage, autre, "9")
    avant = athlete_repository.search(db_session, page_size=500)

    impact = admin_actions.course_deletion_impact(db_session, course_id=cible.id)
    admin_actions.delete_course(db_session, course_id=cible.id, user_id=auteur.id)

    apres = athlete_repository.search(db_session, page_size=500)
    assert impact["participations"] == 4
    assert impact["athletes"] == 3
    assert len(avant) - len(apres) == impact["athletes"]


def test_l_impact_ne_modifie_rien(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "INTACT")
    _inscrit(db_session, coureur, course, "1")

    admin_actions.course_deletion_impact(db_session, course_id=course.id)

    assert course_repository.get(db_session, course.id) is not None
    assert athlete_repository.get(db_session, coureur.id) is not None
    assert participation_repository.count_for_course(db_session, course.id) == 1


def test_l_impact_sur_epreuve_inexistante_refuse(db_session):
    with pytest.raises(NotFoundError):
        admin_actions.course_deletion_impact(db_session, course_id=4242)


# --- Rattacher un résultat (US2) --------------------------------------------


def _duo(db_session):
    course = _epreuve(db_session, "Rattachement")
    source = _coureur(db_session, "SOURCE")
    cible = _coureur(db_session, "CIBLE")
    ligne = _inscrit(db_session, source, course, "1")
    return course, source, cible, ligne


def test_reassign_deplace_le_resultat(db_session, auteur):
    course, source, cible, ligne = _duo(db_session)

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=cible.id, user_id=auteur.id
    )

    assert participation_repository.get(db_session, ligne.id).athlete_id == cible.id
    assert [p.id for p in participation_repository.list_for_athlete(db_session, cible.id)] == [
        ligne.id
    ]


def test_reassign_purge_la_fiche_source_devenue_vide(db_session, auteur):
    course, source, cible, ligne = _duo(db_session)
    source_id = source.id

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=cible.id, user_id=auteur.id
    )

    assert athlete_repository.get(db_session, source_id) is None


def test_reassign_epargne_une_source_encore_pourvue(db_session, auteur):
    course, source, cible, ligne = _duo(db_session)
    autre = _epreuve(db_session, "Autre", date(2026, 7, 1))
    _inscrit(db_session, source, autre, "1")
    source_id = source.id

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=cible.id, user_id=auteur.id
    )

    assert athlete_repository.get(db_session, source_id) is not None


def test_reassign_consigne_l_origine_et_la_destination(db_session, auteur):
    """AC3 — une trace qui ne dirait pas d'où vient le résultat serait illisible."""
    course, source, cible, ligne = _duo(db_session)
    source_id, cible_id = source.id, cible.id

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=cible_id, user_id=auteur.id
    )

    entrees = _journal(db_session, "participation", ligne.id)
    assert len(entrees) == 1
    assert entrees[0].action == "participation.reassign"
    assert entrees[0].payload["from_athlete_id"] == source_id
    assert entrees[0].payload["to_athlete_id"] == cible_id
    assert entrees[0].payload["athletes_purged"] == [source_id]


def test_reassign_vers_un_coureur_deja_classe_refuse(db_session, auteur):
    """FR-006 — sinon la même personne apparaît deux fois au classement."""
    from app.core.exceptions import DuplicateError

    course, source, cible, ligne = _duo(db_session)
    _inscrit(db_session, cible, course, "2")

    with pytest.raises(DuplicateError):
        admin_actions.reassign_participation(
            db_session, participation_id=ligne.id, athlete_id=cible.id, user_id=auteur.id
        )

    assert participation_repository.get(db_session, ligne.id).athlete_id == source.id


def test_reassign_vers_un_coureur_inconnu_refuse(db_session, auteur):
    course, source, cible, ligne = _duo(db_session)

    with pytest.raises(NotFoundError):
        admin_actions.reassign_participation(
            db_session, participation_id=ligne.id, athlete_id=4242, user_id=auteur.id
        )

    assert participation_repository.get(db_session, ligne.id).athlete_id == source.id


def test_reassign_d_un_resultat_inconnu_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.reassign_participation(
            db_session, participation_id=4242, athlete_id=1, user_id=auteur.id
        )


def test_reassign_vers_le_coureur_deja_porteur_ne_consigne_rien(db_session, auteur):
    """FR-012 — une demande qui ne change rien n'est pas un geste.

    Elle réussit (l'état voulu est l'état atteint), mais le journal ne se
    remplit pas de non-événements.
    """
    course, source, cible, ligne = _duo(db_session)

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=source.id, user_id=auteur.id
    )

    assert participation_repository.get(db_session, ligne.id).athlete_id == source.id
    assert _journal(db_session, "participation", ligne.id) == []


# --- Corriger un coureur (US3) ----------------------------------------------


def test_update_athlete_ecrit_les_champs_fournis(db_session, auteur):
    coureur = _coureur(db_session, "DUPOND", "jean")

    admin_actions.update_athlete(
        db_session,
        athlete_id=coureur.id,
        champs={"nom": "DUPONT", "birth_date": date(1988, 3, 2)},
        user_id=auteur.id,
    )

    relu = athlete_repository.get(db_session, coureur.id)
    assert relu.nom == "DUPONT"
    assert relu.birth_date == date(1988, 3, 2)
    assert relu.prenom == "jean"  # non fourni, donc non touché (PATCH strict)


def test_update_athlete_preserve_l_historique(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPOND")
    _inscrit(db_session, coureur, course, "1")

    admin_actions.update_athlete(
        db_session, athlete_id=coureur.id, champs={"nom": "DUPONT"}, user_id=auteur.id
    )

    assert len(participation_repository.list_for_athlete(db_session, coureur.id)) == 1


def test_update_athlete_consigne_l_avant_et_l_apres(db_session, auteur):
    coureur = _coureur(db_session, "DUPOND")

    admin_actions.update_athlete(
        db_session, athlete_id=coureur.id, champs={"nom": "DUPONT"}, user_id=auteur.id
    )

    entrees = _journal(db_session, "athlete", coureur.id)
    assert entrees[0].action == "athlete.update"
    assert entrees[0].payload["before"]["nom"] == "DUPOND"
    assert entrees[0].payload["after"]["nom"] == "DUPONT"


def test_update_athlete_refuse_un_doublon_en_le_nommant(db_session, auteur):
    """AC2 — le message désigne la fiche en conflit, et rien n'est modifié."""
    from app.core.exceptions import DuplicateError

    existant = _coureur(db_session, "DUPONT", "Jean", birth_date=date(1988, 3, 2))
    a_corriger = _coureur(db_session, "DUPOND", "Jean", birth_date=date(1988, 3, 2))

    with pytest.raises(DuplicateError) as capture:
        admin_actions.update_athlete(
            db_session, athlete_id=a_corriger.id, champs={"nom": "DUPONT"}, user_id=auteur.id
        )

    assert str(existant.id) in str(capture.value)
    assert athlete_repository.get(db_session, a_corriger.id).nom == "DUPOND"
    assert _journal(db_session, "athlete", a_corriger.id) == []


def test_update_athlete_sur_coureur_inconnu_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.update_athlete(
            db_session, athlete_id=4242, champs={"nom": "X"}, user_id=auteur.id
        )


def test_update_athlete_sans_changement_ne_consigne_rien(db_session, auteur):
    """Même règle que le rattachement : une demande sans effet n'est pas un geste."""
    coureur = _coureur(db_session, "DUPONT", "Jean")

    admin_actions.update_athlete(
        db_session, athlete_id=coureur.id, champs={"nom": "DUPONT"}, user_id=auteur.id
    )

    assert _journal(db_session, "athlete", coureur.id) == []


# --- Corriger une épreuve (US4) ---------------------------------------------


def test_update_course_ecrit_les_champs_fournis(db_session, auteur):
    course = _epreuve(db_session, "Tri de Nates")

    admin_actions.update_course(
        db_session,
        course_id=course.id,
        champs={"name": "Triathlon de Nantes"},
        user_id=auteur.id,
    )

    assert course_repository.get(db_session, course.id).name == "Triathlon de Nantes"


def test_update_course_ne_touche_aucun_resultat(db_session, auteur):
    """FR-023 — temps, rangs, statut et rattachements identiques avant/après."""
    course = _epreuve(db_session, "Tri de Nates")
    coureur = _coureur(db_session, "COUREUR")
    ligne = _inscrit(db_session, coureur, course, "1")
    ligne.total_time = "01:23:45"
    ligne.rank_overall = 7
    db_session.flush()

    admin_actions.update_course(
        db_session,
        course_id=course.id,
        champs={"name": "Triathlon de Nantes", "event_type": "triathlon-s"},
        user_id=auteur.id,
    )

    relu = participation_repository.get(db_session, ligne.id)
    assert relu.athlete_id == coureur.id
    assert relu.total_time == "01:23:45"
    assert relu.rank_overall == 7
    assert relu.status == "finisher"


def test_update_course_refuse_un_doublon_en_le_nommant(db_session, auteur):
    """FR-021 — le quadruplet (nom, date, type, relais) est la clé d'unicité."""
    from app.core.exceptions import DuplicateError

    existante = _epreuve(db_session, "Triathlon de Nantes", date(2026, 5, 17))
    a_corriger = _epreuve(db_session, "Tri de Nates", date(2026, 5, 17))

    with pytest.raises(DuplicateError) as capture:
        admin_actions.update_course(
            db_session,
            course_id=a_corriger.id,
            champs={"name": "Triathlon de Nantes"},
            user_id=auteur.id,
        )

    assert str(existante.id) in str(capture.value)
    assert course_repository.get(db_session, a_corriger.id).name == "Tri de Nates"


def test_update_course_consigne_l_avant_et_l_apres(db_session, auteur):
    course = _epreuve(db_session, "Tri de Nates")

    admin_actions.update_course(
        db_session,
        course_id=course.id,
        champs={"name": "Triathlon de Nantes"},
        user_id=auteur.id,
    )

    entrees = _journal(db_session, "course", course.id)
    assert entrees[0].action == "course.update"
    assert entrees[0].payload["before"]["name"] == "Tri de Nates"
    assert entrees[0].payload["after"]["name"] == "Triathlon de Nantes"


def test_update_course_sur_epreuve_inconnue_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.update_course(
            db_session, course_id=4242, champs={"name": "X"}, user_id=auteur.id
        )


# --- Re-scraper une épreuve à la demande (#118) -----------------------------


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


@pytest.fixture
def scrape(monkeypatch):
    """Arme le chronométreur entrant — patron de `test_course_source_switch_api.py`."""
    appels: list[str] = []

    def armer(resultats_ou_exception):
        def _scrape(url, **kwargs):
            appels.append(url)
            if isinstance(resultats_ou_exception, Exception):
                raise resultats_ou_exception
            return resultats_ou_exception

        monkeypatch.setattr(import_service, "registry_scrape_event_all", _scrape)
        return appels

    return armer


def _resultat(course, bib, nom, *, event_name=None, prenom="Jean", total_time="01:59:00"):
    return ScrapedResult(
        source_url=course.source_url,
        provider="klikego",
        athlete_name=nom,
        athlete_firstname=prenom,
        bib_number=bib,
        event_name=event_name if event_name is not None else course.name,
        event_date=course.event_date,
        event_type=course.event_type,
        total_time=total_time,
    )


def _rescrapes(db_session, course_id):
    return [
        entree
        for entree in _journal(db_session, "course", course_id)
        if entree.action == "course.rescrape"
    ]


def _attendre(condition, timeout=2.0, intervalle=0.02):
    """Sonde `condition` jusqu'à vrai — le thread de re-scrape termine hors du
    fil qui a itéré le générateur (FR-011), donc son effet n'est visible
    qu'après un délai, jamais synchrone avec le dernier `next()` du test."""
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        try:
            if condition():
                return True
        except Exception:
            pass
        time.sleep(intervalle)
    return condition()


def test_rescrape_upsert_purge_les_orphelins_et_consigne_le_geste(db_session, auteur, scrape):
    """T003 — chemin heureux : upsert par dossard, purge d'orphelin, journal."""
    course = _epreuve(db_session)
    depart = _coureur(db_session, "DEPART")
    reste = _coureur(db_session, "RESTE")
    _inscrit(db_session, depart, course, "1")
    _inscrit(db_session, reste, course, "2")
    db_session.commit()
    # Le dossard 1 change de titulaire chez le chronométreur (réconciliation
    # d'identité) : DEPART n'a alors plus aucune participation → purgé.
    scrape([
        _resultat(course, "1", "NOUVEAU"),
        # Même prénom que `_coureur` (défaut "Coureur") : sinon la réconciliation
        # d'identité (nom + prénom) traiterait RESTE comme un homonyme différent
        # et créerait une seconde fiche, faussant `orphans_removed`.
        _resultat(course, "2", "RESTE", prenom="Coureur", total_time="02:10:00"),
    ])

    events = list(admin_actions.iter_rescrape_course(
        db_session, course_id=course.id, user_id=auteur.id, settings=_settings()
    ))

    assert events[-1]["phase"] == "done"
    assert events[-1]["orphans_removed"] == 1
    assert participation_repository.count_for_course(db_session, course.id) == 2
    assert athlete_repository.get(db_session, depart.id) is None
    assert athlete_repository.get(db_session, reste.id) is not None
    entrees = _rescrapes(db_session, course.id)
    assert len(entrees) == 1
    assert entrees[0].payload["athletes_purged"] == 1
    assert entrees[0].payload["source_url"] == course.source_url


def test_rescrape_refuse_zero_resultat_et_ne_modifie_rien(db_session, auteur, scrape):
    """T005 — FR-009."""
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "INTACT")
    _inscrit(db_session, coureur, course, "1")
    db_session.commit()
    scrape([])

    events = list(admin_actions.iter_rescrape_course(
        db_session, course_id=course.id, user_id=auteur.id, settings=_settings()
    ))

    assert events[-1]["phase"] == "error"
    assert "aucun résultat" in events[-1]["message"].lower()
    assert participation_repository.count_for_course(db_session, course.id) == 1
    assert _rescrapes(db_session, course.id) == []


def test_rescrape_refuse_une_epreuve_divergente_et_ne_modifie_rien(db_session, auteur, scrape):
    """T006 — FR-009."""
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "INTACT")
    _inscrit(db_session, coureur, course, "1")
    db_session.commit()
    scrape([_resultat(course, "9", "AUTRE", event_name="Une tout autre épreuve")])

    events = list(admin_actions.iter_rescrape_course(
        db_session, course_id=course.id, user_id=auteur.id, settings=_settings()
    ))

    assert events[-1]["phase"] == "error"
    assert "Une tout autre épreuve" in events[-1]["message"]
    assert participation_repository.count_for_course(db_session, course.id) == 1
    assert _rescrapes(db_session, course.id) == []


def test_rescrape_termine_et_commite_malgre_un_client_qui_arrete_de_lire(
    db_session, auteur, scrape,
):
    """T007 — FR-011 : le thread de fond persiste même si le générateur est
    abandonné à mi-flux (les deux premiers events seuls sont consommés).

    `ponytail:` `db_session` est ensuite lu (`_attendre`) depuis le fil de
    test pendant que le thread de fond peut encore l'écrire — inévitable pour
    éprouver ce comportement pour de vrai, sur le même patron que
    `_scrape_all_streaming` en production. Amorti par le polling/retry
    d'`_attendre` (ré-essaie sur exception), pas par une garantie de
    non-concurrence — un flake occasionnel sous forte contention CI est
    possible ; sans impact production, où le générateur qui pilote le thread
    ne touche jamais `db` en parallèle de lui (cf. `_stream_rescrape`)."""
    course = _epreuve(db_session)
    db_session.commit()
    scrape([_resultat(course, "1", "NOUVEAU")])

    gen = admin_actions.iter_rescrape_course(
        db_session, course_id=course.id, user_id=auteur.id, settings=_settings()
    )
    for i, _event in enumerate(gen):
        if i >= 1:
            break  # le client cesse de lire — `gen` n'est plus jamais itéré

    assert _attendre(
        lambda: participation_repository.count_for_course(db_session, course.id) == 1
    )
    assert _attendre(lambda: len(_rescrapes(db_session, course.id)) == 1)


def test_rescrape_ajoute_les_dossards_manquants_sans_dupliquer(db_session, auteur, scrape):
    """T016 — US2 : rejouer un import partiel complète sans dupliquer."""
    course = _epreuve(db_session)
    deja_la = _coureur(db_session, "DEJA-LA")
    _inscrit(db_session, deja_la, course, "1")
    db_session.commit()
    scrape([
        _resultat(course, "1", "DEJA-LA"),
        _resultat(course, "2", "MANQUANT"),
    ])

    events = list(admin_actions.iter_rescrape_course(
        db_session, course_id=course.id, user_id=auteur.id, settings=_settings()
    ))

    assert events[-1]["phase"] == "done"
    assert participation_repository.count_for_course(db_session, course.id) == 2
    dossards = sorted(
        p.bib_number for p in participation_repository.list_for_course(db_session, course.id)
    )
    assert dossards == ["1", "2"]


def test_rescrape_refuse_un_second_declenchement_sur_la_meme_course(db_session, auteur):
    """T017 — FR-007/SC-005, premier volet : même course, refusé."""
    course = _epreuve(db_session)
    db_session.commit()

    admin_actions._acquire_rescrape_lock(course.id)
    try:
        with pytest.raises(admin_actions.CourseRescrapeAlreadyRunningError):
            admin_actions.iter_rescrape_course(
                db_session, course_id=course.id, user_id=auteur.id, settings=_settings()
            )
    finally:
        admin_actions._release_rescrape_lock(course.id)


def test_rescrape_sur_une_autre_course_n_est_pas_bloque(db_session, auteur, scrape):
    """T017 — second volet : le refus ne porte que sur la même course."""
    course_a = _epreuve(db_session, "Course A", date(2026, 5, 17))
    course_b = _epreuve(db_session, "Course B", date(2026, 5, 18))
    db_session.commit()
    scrape([_resultat(course_b, "1", "X")])

    admin_actions._acquire_rescrape_lock(course_a.id)
    try:
        events = list(admin_actions.iter_rescrape_course(
            db_session, course_id=course_b.id, user_id=auteur.id, settings=_settings()
        ))
        assert events[-1]["phase"] == "done"
    finally:
        admin_actions._release_rescrape_lock(course_a.id)


def test_rescrape_sur_course_sans_source_active_est_un_not_found(db_session, auteur):
    """G4 — saisie manuelle ou épreuve dont on n'a rattaché que des passives :
    rien à re-scraper, refus explicite plutôt qu'un flux qui ne ferait rien."""
    course = course_repository.get_or_create(
        db_session, name="Saisie manuelle", event_date=date(2026, 6, 1),
        event_type="triathlon-m",
    )
    db_session.commit()

    with pytest.raises(NotFoundError):
        admin_actions.iter_rescrape_course(
            db_session, course_id=course.id, user_id=auteur.id, settings=_settings()
        )


def test_rescrape_sur_course_inconnue_est_un_not_found(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.iter_rescrape_course(
            db_session, course_id=4242, user_id=auteur.id, settings=_settings()
        )


# --- Purger tous les résultats (#384) ---------------------------------------


def _epreuve_avec_resultat(db_session, nom, dossard, event_date=date(2026, 5, 17)):
    """Une épreuve, un athlète, une participation, `scraped_at` posé — pour la purge.

    `participation_repository` est déjà importé en tête de ce fichier."""
    course = _epreuve(db_session, nom, event_date)
    # `dossard` distingue l'athlète d'un appel à l'autre : `_coureur` dédoublonne
    # par identité (nom, prénom, date de naissance), et "COUREUR"/"Jean" fixe
    # pour tout appel referait le même athlète au lieu d'un par épreuve.
    athlete = _coureur(db_session, f"COUREUR{dossard}", "Jean")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=dossard, club="TCN"
    )
    course_repository.touch_scraped_at(db_session, course)
    db_session.flush()
    return course, athlete


def test_wipe_impact_chiffre_participations_et_athletes(db_session):
    _epreuve_avec_resultat(db_session, "Tri A", "1")
    _epreuve_avec_resultat(db_session, "Tri B", "2")

    impact = admin_actions.wipe_impact(db_session)

    assert impact == {"participations": 2, "athletes": 2}


def test_wipe_impact_ne_modifie_rien(db_session):
    _epreuve_avec_resultat(db_session, "Tri A", "1")

    admin_actions.wipe_impact(db_session)

    assert participation_repository.count_all(db_session) == 1
    assert athlete_repository.count_all(db_session) == 1


def test_wipe_all_participations_vide_la_table_et_laisse_les_courses_intactes(
    db_session, auteur
):
    course_a, _ = _epreuve_avec_resultat(db_session, "Tri A", "1")
    course_b, _ = _epreuve_avec_resultat(db_session, "Tri B", "2")

    resume = admin_actions.wipe_all_participations(db_session, user_id=auteur.id)

    assert resume == {
        "participations_deleted": 2,
        "athletes_purged": 2,
        "courses_reset": 2,
    }
    assert participation_repository.count_all(db_session) == 0
    assert athlete_repository.count_all(db_session) == 0
    assert course_repository.get(db_session, course_a.id) is not None
    assert course_repository.get(db_session, course_b.id) is not None


def test_wipe_all_participations_remet_scraped_at_a_null(db_session, auteur):
    course, _ = _epreuve_avec_resultat(db_session, "Tri A", "1")
    assert course.scraped_at is not None

    admin_actions.wipe_all_participations(db_session, user_id=auteur.id)

    db_session.expire(course)
    assert course_repository.get(db_session, course.id).scraped_at is None


def test_wipe_all_participations_consigne_le_geste(db_session, auteur):
    """Le journal ne garde que les deux compteurs annoncés par `wipe_impact` — pas
    `courses_reset`, absent de la spec de l'issue #384 (« payload = les deux
    compteurs »), même s'il reste dans la valeur de retour pour l'appelant."""
    _epreuve_avec_resultat(db_session, "Tri A", "1")

    admin_actions.wipe_all_participations(db_session, user_id=auteur.id)

    entrees = _journal(db_session, "participations", 0)
    assert [e.action for e in entrees] == ["participations.wipe_all"]
    assert entrees[0].payload == {"participations_deleted": 1, "athletes_purged": 1}


def test_wipe_all_participations_sur_base_vide_ne_consigne_rien_a_tort(db_session, auteur):
    """Une base déjà vide reste un geste réel (compteurs à 0), pas un no-op tu."""
    resume = admin_actions.wipe_all_participations(db_session, user_id=auteur.id)

    assert resume == {"participations_deleted": 0, "athletes_purged": 0, "courses_reset": 0}
    entrees = _journal(db_session, "participations", 0)
    assert [e.action for e in entrees] == ["participations.wipe_all"]


# --- Purger toutes les épreuves (#384, suite) --------------------------------


def test_courses_wipe_impact_chiffre_courses_participations_et_athletes(db_session):
    _epreuve_avec_resultat(db_session, "Tri A", "1")
    _epreuve_avec_resultat(db_session, "Tri B", "2")

    impact = admin_actions.courses_wipe_impact(db_session)

    assert impact == {"courses": 2, "participations": 2, "athletes": 2}


def test_courses_wipe_impact_ne_modifie_rien(db_session):
    course, _ = _epreuve_avec_resultat(db_session, "Tri A", "1")

    admin_actions.courses_wipe_impact(db_session)

    assert course_repository.get(db_session, course.id) is not None
    assert participation_repository.count_all(db_session) == 1
    assert athlete_repository.count_all(db_session) == 1


def test_wipe_all_courses_supprime_courses_sources_et_resultats(db_session, auteur):
    _epreuve_avec_resultat(db_session, "Tri A", "1")
    _epreuve_avec_resultat(db_session, "Tri B", "2")

    resume = admin_actions.wipe_all_courses(db_session, user_id=auteur.id)

    assert resume == {"courses_deleted": 2, "athletes_purged": 2}
    # Lecture agrégée fraîche, pas `course_repository.get` sur les objets
    # `course_a`/`course_b` : `delete_all` est un DELETE de masse qui ne
    # périme pas l'identity map (même choix que `participation_repository
    # .delete_all`) — les relire par ORM sur cette session testerait une
    # staleté connue et acceptée, pas le comportement du service.
    assert course_repository.count_all(db_session) == 0
    assert participation_repository.count_all(db_session) == 0
    assert athlete_repository.count_all(db_session) == 0


def test_wipe_all_courses_consigne_le_geste(db_session, auteur):
    _epreuve_avec_resultat(db_session, "Tri A", "1")

    admin_actions.wipe_all_courses(db_session, user_id=auteur.id)

    entrees = _journal(db_session, "courses", 0)
    assert [e.action for e in entrees] == ["courses.wipe_all"]
    assert entrees[0].payload == {"courses_deleted": 1, "athletes_purged": 1}


def test_wipe_all_courses_sur_base_vide_ne_consigne_rien_a_tort(db_session, auteur):
    """Même règle que `wipe_all_participations` : une base vide reste un geste réel."""
    resume = admin_actions.wipe_all_courses(db_session, user_id=auteur.id)

    assert resume == {"courses_deleted": 0, "athletes_purged": 0}
    entrees = _journal(db_session, "courses", 0)
    assert [e.action for e in entrees] == ["courses.wipe_all"]


# --- Valider un résultat en attente (#271, US1) ------------------------------


def test_validate_participation_leve_l_etat_pendant(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.validate_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    assert participation_repository.get(db_session, ligne.id).is_pending_validation is False


def test_validate_participation_consigne_le_geste(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.validate_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    entrees = _journal(db_session, "participation", ligne.id)
    assert len(entrees) == 1
    assert entrees[0].action == "participation.validate"
    assert entrees[0].user_id == auteur.id


def test_validate_participation_deja_validee_ne_consigne_pas_un_second_geste(db_session, auteur):
    """FR-012 — patron de `reassign_participation` : l'état voulu est déjà atteint."""
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=False,
    )
    db_session.flush()

    admin_actions.validate_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    assert _journal(db_session, "participation", ligne.id) == []


def test_validate_participation_sur_resultat_inconnu_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.validate_participation(db_session, participation_id=4242, user_id=auteur.id)


# --- Signaler/dé-signaler un résultat non conforme (#437) -------------------


def test_reject_participation_pose_is_rejected(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.reject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    rechargee = participation_repository.get(db_session, ligne.id)
    assert rechargee.is_rejected is True
    assert rechargee.is_pending_validation is True  # jamais touché (#437)


def test_reject_participation_consigne_le_geste(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.reject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    entrees = _journal(db_session, "participation", ligne.id)
    assert [e.action for e in entrees] == ["participation.reject"]


def test_reject_participation_deja_rejetee_ne_consigne_pas_un_second_geste(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, is_rejected=True,
    )
    db_session.flush()

    admin_actions.reject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    assert _journal(db_session, "participation", ligne.id) == []


def test_reject_participation_sur_resultat_inconnu_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.reject_participation(db_session, participation_id=4242, user_id=auteur.id)


def test_unreject_participation_leve_is_rejected(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, is_rejected=True,
    )
    db_session.flush()

    admin_actions.unreject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    assert participation_repository.get(db_session, ligne.id).is_rejected is False


def test_unreject_participation_deja_actionnable_ne_consigne_pas_un_second_geste(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, is_rejected=False,
    )
    db_session.flush()

    admin_actions.unreject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    assert _journal(db_session, "participation", ligne.id) == []

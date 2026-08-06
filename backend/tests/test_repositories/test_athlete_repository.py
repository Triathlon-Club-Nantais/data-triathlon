from datetime import date

from app.repositories import athlete_repository


def test_get_or_create_creates_then_dedups(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    assert a1.id is not None

    # Même identité, casse différente → même athlète
    a2 = athlete_repository.get_or_create(db_session, nom="dupont", prenom="jean")
    assert a2.id == a1.id


def test_birth_date_distinguishes_homonyms(db_session):
    a1 = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1990, 1, 1)
    )
    a2 = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1985, 6, 2)
    )
    assert a1.id != a2.id


def test_get_or_create_updates_current_club(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="DURAND", prenom="Lucie", club="TCN")
    a2 = athlete_repository.get_or_create(
        db_session, nom="DURAND", prenom="Lucie", club="Triathlon Club Nantais"
    )
    assert a2.id == a1.id
    assert a2.club == "Triathlon Club Nantais"


def test_search_by_name(db_session):
    athlete_repository.get_or_create(db_session, nom="LEROY", prenom="Anne", club="TCN")
    athlete_repository.get_or_create(db_session, nom="MOREAU", prenom="Eric", club="TCN")
    db_session.flush()

    found = athlete_repository.search(db_session, name="lero")
    assert [a.nom for a in found] == ["LEROY"]


def test_get_or_create_dedup_noms_accentues(db_session):
    """`lower()` de SQLite ignore les accents majuscules ('LEMÉE' → 'lemÉe').

    Sans fonction Unicode-aware, chaque import recréait un athlète accentué.
    """
    a1 = athlete_repository.get_or_create(db_session, nom="LEMÉE", prenom="Sébastien")
    a2 = athlete_repository.get_or_create(db_session, nom="LEMÉE", prenom="Sébastien")
    assert a2.id == a1.id


def test_get_or_create_dedup_accents_casse_mixte(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="LEMÉE", prenom="Sébastien")
    a2 = athlete_repository.get_or_create(db_session, nom="lemée", prenom="sébastien")
    assert a2.id == a1.id


def test_resolve_signale_creation_puis_reutilisation(db_session):
    a1, cree1 = athlete_repository.resolve(db_session, nom="ROUX", prenom="Alexis")
    assert cree1 is True
    a2, cree2 = athlete_repository.resolve(db_session, nom="ROUX", prenom="Alexis")
    assert cree2 is False
    assert a2.id == a1.id


def _course_avec_participation(db_session, nom_athlete):
    from app.repositories import course_repository, participation_repository

    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=None, event_type="triathlon-m",
        source_url="https://k/x", provider="klikego",
    )
    athlete = athlete_repository.get_or_create(db_session, nom=nom_athlete, prenom="X")
    db_session.flush()
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
    )
    db_session.flush()
    return athlete


def test_delete_orphans_supprime_les_sans_participation(db_session):
    rattache = _course_avec_participation(db_session, "RATTACHE")
    orphelin = athlete_repository.get_or_create(db_session, nom="ORPHELIN", prenom="O")
    db_session.flush()

    n = athlete_repository.delete_orphans(db_session)

    assert n == 1
    assert athlete_repository.get(db_session, orphelin.id) is None
    assert athlete_repository.get(db_session, rattache.id) is not None


def test_delete_orphans_no_op_sur_base_saine(db_session):
    """Garde de non-régression : 0 orphelin aujourd'hui → la règle n'emporte rien."""
    _course_avec_participation(db_session, "RATTACHE")

    assert athlete_repository.delete_orphans(db_session) == 0


def _epreuve(db_session, nom_epreuve):
    from app.repositories import course_repository

    course = course_repository.get_or_create(
        db_session, name=nom_epreuve, event_date=None, event_type="triathlon-m",
        source_url=f"https://k/{nom_epreuve}", provider="klikego",
    )
    db_session.flush()
    return course


def _inscrit(db_session, athlete, course, dossard="1"):
    from app.repositories import participation_repository

    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=dossard
    )
    db_session.flush()


def test_only_on_course_ne_rend_que_les_exclusifs(db_session):
    """FR-026 — ceux que la suppression de cette épreuve laisserait sans rien.

    Un coureur présent aussi ailleurs n'est **pas** menacé : c'est toute la
    différence entre « inscrit à cette épreuve » et « n'a que cette épreuve ».
    """
    cible = _epreuve(db_session, "Cible")
    autre = _epreuve(db_session, "Autre")
    exclusif = athlete_repository.get_or_create(db_session, nom="EXCLUSIF", prenom="E")
    partage = athlete_repository.get_or_create(db_session, nom="PARTAGE", prenom="P")
    ailleurs = athlete_repository.get_or_create(db_session, nom="AILLEURS", prenom="A")
    db_session.flush()
    _inscrit(db_session, exclusif, cible, "1")
    _inscrit(db_session, partage, cible, "2")
    _inscrit(db_session, partage, autre, "2")
    _inscrit(db_session, ailleurs, autre, "3")

    menaces = athlete_repository.only_on_course(db_session, cible.id)

    assert menaces == [exclusif.id]


def test_only_on_course_ne_modifie_rien(db_session):
    """La route d'impact est une lecture : elle chiffre, elle ne prépare pas."""
    cible = _epreuve(db_session, "Cible")
    athlete = athlete_repository.get_or_create(db_session, nom="INTACT", prenom="I")
    db_session.flush()
    _inscrit(db_session, athlete, cible)

    athlete_repository.only_on_course(db_session, cible.id)

    assert athlete_repository.get(db_session, athlete.id) is not None


def test_delete_orphans_among_ne_touche_que_les_ids_fournis(db_session):
    vise = athlete_repository.get_or_create(db_session, nom="VISE", prenom="V")
    hors_liste = athlete_repository.get_or_create(db_session, nom="HORSLISTE", prenom="H")
    db_session.flush()

    supprimes = athlete_repository.delete_orphans_among(db_session, [vise.id])

    assert supprimes == [vise.id]
    assert athlete_repository.get(db_session, vise.id) is None
    assert athlete_repository.get(db_session, hors_liste.id) is not None


def test_delete_orphans_among_epargne_un_id_encore_rattache(db_session):
    """Fourni ≠ orphelin : la fonction vérifie, elle n'obéit pas aveuglément."""
    course = _epreuve(db_session, "Course")
    rattache = athlete_repository.get_or_create(db_session, nom="RATTACHE2", prenom="R")
    db_session.flush()
    _inscrit(db_session, rattache, course)

    supprimes = athlete_repository.delete_orphans_among(db_session, [rattache.id])

    assert supprimes == []
    assert athlete_repository.get(db_session, rattache.id) is not None


def test_delete_orphans_among_sans_ids_balaie_toute_la_base(db_session):
    """`None` = pas de restriction — c'est ce que `delete_orphans()` appelle."""
    orphelin = athlete_repository.get_or_create(db_session, nom="ORPHELIN2", prenom="O")
    db_session.flush()

    supprimes = athlete_repository.delete_orphans_among(db_session)

    assert supprimes == [orphelin.id]


def test_delete_orphans_among_sur_liste_vide_ne_balaie_rien(db_session):
    """Le piège du `None` : `[]` veut dire « aucun candidat », pas « tous ».

    Sans cette distinction, une suppression d'épreuve sans orphelin emporterait
    tous les orphelins préexistants de la base.
    """
    orphelin = athlete_repository.get_or_create(db_session, nom="ORPHELIN3", prenom="O")
    db_session.flush()

    supprimes = athlete_repository.delete_orphans_among(db_session, [])

    assert supprimes == []
    assert athlete_repository.get(db_session, orphelin.id) is not None


def test_delete_orphans_garde_son_contrat_d_entier(db_session):
    """Non-régression de `rescrape_service` : `orphans_removed` reste un `int`."""
    athlete_repository.get_or_create(db_session, nom="ORPHELIN4", prenom="O")
    db_session.flush()

    resultat = athlete_repository.delete_orphans(db_session)

    assert isinstance(resultat, int)
    assert resultat == 1


def test_search_admin_rend_l_identite_complete_et_le_compte(db_session):
    """FR-024 — de quoi départager deux homonymes avant un geste sans retour."""
    course = _epreuve(db_session, "Pour compter")
    jean = athlete_repository.get_or_create(
        db_session, nom="DUPONT", prenom="Jean", birth_date=date(1988, 3, 2), club="TCN"
    )
    db_session.flush()
    _inscrit(db_session, jean, course, "1")

    resultats = athlete_repository.search_admin(db_session, search="dupont")

    assert len(resultats) == 1
    athlete, nombre = resultats[0]
    assert athlete.nom == "DUPONT"
    assert athlete.birth_date == date(1988, 3, 2)
    assert athlete.club == "TCN"
    assert nombre == 1


def test_search_admin_distingue_deux_homonymes_par_leur_compte(db_session):
    """Le cas d'usage réel : deux fiches, même nom, même club, à départager."""
    course = _epreuve(db_session, "Homonymes")
    autre = _epreuve(db_session, "Homonymes 2")
    prolifique = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1990, 1, 1), club="TCN"
    )
    rare = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1985, 6, 2), club="TCN"
    )
    db_session.flush()
    _inscrit(db_session, prolifique, course, "1")
    _inscrit(db_session, prolifique, autre, "1")
    _inscrit(db_session, rare, course, "2")

    par_id = {a.id: n for a, n in athlete_repository.search_admin(db_session, search="martin")}

    assert par_id[prolifique.id] == 2
    assert par_id[rare.id] == 1


def test_search_admin_compte_zero_sans_participation(db_session):
    """Une fiche vide doit rester visible : c'est souvent celle qu'on corrige."""
    athlete_repository.get_or_create(db_session, nom="SANSRESULTAT", prenom="S")
    db_session.flush()

    resultats = athlete_repository.search_admin(db_session, search="sansresultat")

    assert [n for _, n in resultats] == [0]


def test_search_admin_cherche_aussi_dans_le_prenom(db_session):
    athlete_repository.get_or_create(db_session, nom="LEROY", prenom="Anne-Sophie")
    db_session.flush()

    assert len(athlete_repository.search_admin(db_session, search="sophie")) == 1

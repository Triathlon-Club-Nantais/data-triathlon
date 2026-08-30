from datetime import date

from app.repositories import athlete_repository, course_repository, participation_repository


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


def test_une_fiche_nee_d_un_import_suit_l_import(db_session):
    """#439, INV-2 — le drapeau naît faux : sans correction humaine, rien ne change."""
    athlete = athlete_repository.get_or_create(
        db_session, nom="NOUVEAU", prenom="Nino", club="TCN"
    )
    assert athlete.club_locked is False


def test_resolve_ne_reecrit_pas_un_club_verrouille(db_session):
    """#439, INV-1 — la correction humaine prime sur tout import ultérieur.

    C'est le seul point d'application de l'invariant : `resolve` est le seul
    écrivain de `Athlete.club` après création, donc aucun chemin d'import ne peut
    le contourner.
    """
    athlete = athlete_repository.get_or_create(
        db_session, nom="VERROU", prenom="Vera", club="ASPTT NANTES"
    )
    athlete.club_locked = True
    db_session.flush()

    de_nouveau, cree = athlete_repository.resolve(
        db_session, nom="VERROU", prenom="Vera", club="TRI CLUB NANTAIS"
    )

    assert cree is False
    assert de_nouveau.club == "ASPTT NANTES"


def test_search_by_name(db_session):
    athlete_repository.get_or_create(db_session, nom="LEROY", prenom="Anne", club="TCN")
    athlete_repository.get_or_create(db_session, nom="MOREAU", prenom="Eric", club="TCN")
    db_session.flush()

    found = athlete_repository.search(db_session, name="lero")
    assert [a.nom for a in found] == ["LEROY"]


def test_search_par_prenom_nom(db_session):
    """« prénom nom » : chaque mot doit matcher nom **ou** prénom (#357)."""
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul")
    db_session.flush()

    found = athlete_repository.search(db_session, name="Jean Dupont")

    assert [a.nom for a in found] == ["DUPONT"]


def test_search_par_nom_prenom(db_session):
    """L'ordre des mots ne compte pas : « nom prénom » trouve aussi."""
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    db_session.flush()

    found = athlete_repository.search(db_session, name="Dupont Jean")

    assert [a.nom for a in found] == ["DUPONT"]


def test_search_par_prenom_nom_accentue(db_session):
    """Nom accentué + deux mots : « Sébastien Lemée » trouve « LEMÉE »."""
    athlete_repository.get_or_create(db_session, nom="LEMÉE", prenom="Sébastien")
    db_session.flush()

    found = athlete_repository.search(db_session, name="sebastien lemee")

    assert [a.nom for a in found] == ["LEMÉE"]


def test_search_avec_terme_tout_espaces_ne_rend_rien(db_session):
    """`name="   "` ne doit pas dégénérer en absence de filtre (revue #365)."""
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    db_session.flush()

    found = athlete_repository.search(db_session, name="   ")

    assert found == []


def test_search_admin_avec_terme_tout_espaces_ne_rend_rien(db_session):
    """Même garde côté recherche gardée (revue #365)."""
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    db_session.flush()

    resultats = athlete_repository.search_admin(db_session, search="   ")

    assert resultats == []


def test_search_admin_par_prenom_nom(db_session):
    """La recherche gardée passe aussi par le filtre mot à mot (#357)."""
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Marie")
    db_session.flush()

    resultats = athlete_repository.search_admin(db_session, search="jean dupont")

    assert [a.prenom for a, _ in resultats] == ["Jean"]


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


# ── list_with_season_participation_count (issue #274) ───────────────────────


def _epreuve_datee(db_session, nom_epreuve, event_date):
    from app.repositories import course_repository

    course = course_repository.get_or_create(
        db_session, name=nom_epreuve, event_date=event_date, event_type="triathlon-m",
        source_url=f"https://k/{nom_epreuve}", provider="klikego",
    )
    db_session.flush()
    return course


def _inscrit_club(db_session, athlete, course, dossard, club="TCN"):
    from app.repositories import participation_repository

    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=dossard, club=club,
    )
    db_session.flush()


def test_saison_ne_rend_que_les_athletes_avec_participation_dessus(db_session):
    """FR-002 — jointure interne : 0 participation sur la saison ⇒ absent, pas à 0."""
    course_2025 = _epreuve_datee(db_session, "Saison 2025", date(2025, 10, 1))
    course_2024 = _epreuve_datee(db_session, "Saison 2024", date(2024, 10, 1))
    actif = athlete_repository.get_or_create(db_session, nom="ACTIF", prenom="A", club="TCN")
    ancien = athlete_repository.get_or_create(db_session, nom="ANCIEN", prenom="A", club="TCN")
    db_session.flush()
    _inscrit_club(db_session, actif, course_2025, "1")
    _inscrit_club(db_session, ancien, course_2024, "1")

    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=False
    )

    assert [a.nom for a, *_ in resultats] == ["ACTIF"]


def test_saison_compte_les_participations_de_l_athlete_sur_la_saison(db_session):
    course1 = _epreuve_datee(db_session, "Une", date(2025, 9, 15))
    course2 = _epreuve_datee(db_session, "Deux", date(2026, 3, 1))
    athlete = athlete_repository.get_or_create(db_session, nom="PROLIFIQUE", prenom="P", club="TCN")
    db_session.flush()
    _inscrit_club(db_session, athlete, course1, "1")
    _inscrit_club(db_session, athlete, course2, "2")

    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=False
    )

    assert resultats == [(athlete, 2, 2, 2)]


def test_saison_club_only_filtre_sur_le_club_de_lathlete_pas_de_la_participation(db_session):
    """#709 (issue) — la sélection du roster porte sur `Athlete.club` (comme
    `search()`), pas sur `Participation.club` : un membre confirmé du club
    reste dans la liste même si le fournisseur ne publie pas l'affiliation
    club sur la ligne de résultat (research.md D1)."""
    course = _epreuve_datee(db_session, "Filtre club", date(2025, 9, 15))
    membre = athlete_repository.get_or_create(db_session, nom="MEMBRE", prenom="M", club="Triathlon Club Nantais")
    exterieur = athlete_repository.get_or_create(db_session, nom="EXTERIEUR", prenom="E", club="Un Autre Club")
    db_session.flush()
    # Ni l'un ni l'autre n'a d'affiliation club publiée sur la ligne de résultat.
    _inscrit_club(db_session, membre, course, "1", club=None)
    _inscrit_club(db_session, exterieur, course, "2", club=None)

    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=True
    )

    assert [a.nom for a, *_ in resultats] == ["MEMBRE"]


def test_saison_trois_compteurs_distincts(db_session):
    """#709 (issue) — total réel / validées / affiliées club sont trois
    agrégats indépendants sur les mêmes lignes (research.md D2)."""
    from app.repositories import participation_repository

    course_affiliee = _epreuve_datee(db_session, "Affiliée club", date(2025, 9, 15))
    course_sans_affiliation = _epreuve_datee(db_session, "Sans affiliation", date(2025, 10, 1))
    course_en_attente = _epreuve_datee(db_session, "En attente", date(2025, 11, 1))
    athlete = athlete_repository.get_or_create(
        db_session, nom="MULTI", prenom="M", club="Triathlon Club Nantais"
    )
    db_session.flush()
    # Validée + affiliée club.
    _inscrit_club(db_session, athlete, course_affiliee, "1", club="Triathlon Club Nantais")
    # Validée mais sans affiliation club publiée par le fournisseur.
    _inscrit_club(db_session, athlete, course_sans_affiliation, "2", club=None)
    # En attente de validation (compte dans le total réel, pas dans les deux autres).
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course_en_attente.id,
        bib_number="3",
        club="Triathlon Club Nantais",
        is_pending_validation=True,
    )
    db_session.flush()

    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=True
    )

    assert len(resultats) == 1
    _, total, validees, affiliees_club = resultats[0]
    assert (total, validees, affiliees_club) == (3, 2, 1)


def test_saison_trie_par_nom_puis_prenom(db_session):
    course = _epreuve_datee(db_session, "Tri", date(2025, 9, 15))
    zebre = athlete_repository.get_or_create(db_session, nom="ZEBRE", prenom="Z", club="TCN")
    alpha = athlete_repository.get_or_create(db_session, nom="ALPHA", prenom="A", club="TCN")
    db_session.flush()
    _inscrit_club(db_session, zebre, course, "1")
    _inscrit_club(db_session, alpha, course, "2")

    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=False
    )

    assert [a.nom for a, *_ in resultats] == ["ALPHA", "ZEBRE"]


def test_saison_nom_vide_en_fin_de_tri(db_session):
    """Edge Cases du spec — un nom mal renseigné ne fait pas échouer le tri,
    et ne se retrouve pas non plus en tête d'une liste alphabétique."""
    course = _epreuve_datee(db_session, "Nom vide", date(2025, 9, 15))
    sans_nom = athlete_repository.get_or_create(db_session, nom="", prenom="X", club="TCN")
    alpha = athlete_repository.get_or_create(db_session, nom="ALPHA", prenom="A", club="TCN")
    db_session.flush()
    _inscrit_club(db_session, sans_nom, course, "1")
    _inscrit_club(db_session, alpha, course, "2")

    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=False
    )

    assert [a.nom for a, *_ in resultats] == ["ALPHA", ""]


def test_saison_vide_sans_seasons_ne_filtre_pas_la_date(db_session):
    """`seasons=[]` (neutre, Principe V) : toutes saisons confondues, pas de résultat vide."""
    course = _epreuve_datee(db_session, "Neutre", date(2020, 9, 15))
    athlete = athlete_repository.get_or_create(db_session, nom="TOUTESSAISONS", prenom="T", club="TCN")
    db_session.flush()
    _inscrit_club(db_session, athlete, course, "1")

    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[], club_only=False
    )

    assert [a.nom for a, *_ in resultats] == ["TOUTESSAISONS"]


def test_count_all_compte_toute_la_base(db_session):
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul")
    db_session.flush()

    assert athlete_repository.count_all(db_session) == 2


def test_saison_federal_only_retire_les_disciplines_hors_federation(db_session):
    """#382 — même défaut neutre (`federal_only=False`) et même liste d'exclusion que #76."""
    from app.repositories import course_repository

    course_tri = _epreuve_datee(db_session, "Triathlon", date(2025, 9, 15))
    course_trail = course_repository.get_or_create(
        db_session, name="Trail", event_date=date(2025, 9, 20), event_type="trail",
        source_url="https://k/Trail", provider="klikego",
    )
    db_session.flush()
    triathlete = athlete_repository.get_or_create(db_session, nom="TRIATHLETE", prenom="T", club="TCN")
    traileur = athlete_repository.get_or_create(db_session, nom="TRAILEUR", prenom="T", club="TCN")
    db_session.flush()
    _inscrit_club(db_session, triathlete, course_tri, "1")
    _inscrit_club(db_session, traileur, course_trail, "2")

    resultats = athlete_repository.list_with_season_participation_count(
        db_session, seasons=[2025], club_only=False, federal_only=True
    )

    assert [a.nom for a, *_ in resultats] == ["TRIATHLETE"]


# ── search_by_relevance (issue #484, NAV-8) ───────────────────────────────


def test_search_by_relevance_classe_prefixe_avant_sous_chaine_malgre_le_volume(db_session):
    """Preuve de terrain NAV-8 (audit § 5) : un préfixe exact bat toujours une
    sous-chaîne en milieu de nom, quel que soit le volume de courses."""
    prefixe = athlete_repository.get_or_create(db_session, nom="HERRMANN", prenom="Mathieu")
    milieu = athlete_repository.get_or_create(db_session, nom="CHERRUEAU", prenom="Yves")
    db_session.flush()
    _inscrit(db_session, prefixe, _epreuve(db_session, "P1"), "1")
    for i in range(5):
        _inscrit(db_session, milieu, _epreuve(db_session, f"P-milieu-{i}"), "1")
    db_session.commit()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr")

    assert [a.nom for a, _ in resultats] == ["HERRMANN", "CHERRUEAU"]


def test_search_by_relevance_classe_les_trois_paliers(db_session):
    """0 = préfixe exact, 1 = début de mot (après espace/trait d'union), 2 = sous-chaîne."""
    athlete_repository.get_or_create(db_session, nom="HERRMANN", prenom="Anna")
    athlete_repository.get_or_create(db_session, nom="DUBOIS-HERRY", prenom="Alex")
    athlete_repository.get_or_create(db_session, nom="CHERRUEAU", prenom="Yves")
    db_session.flush()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr")

    assert [a.nom for a, _ in resultats] == ["HERRMANN", "DUBOIS-HERRY", "CHERRUEAU"]


def test_search_by_relevance_departage_par_volume_dans_un_meme_palier(db_session):
    """Deux préfixes exacts : le volume reste le départage à l'intérieur d'un
    même palier — « avant le volume » ne s'applique qu'entre paliers différents."""
    peu_couru = athlete_repository.get_or_create(db_session, nom="HERRMANN", prenom="Mathieu")
    tres_couru = athlete_repository.get_or_create(db_session, nom="HERRY", prenom="Yves")
    db_session.flush()
    _inscrit(db_session, peu_couru, _epreuve(db_session, "P1"), "1")
    for i in range(5):
        _inscrit(db_session, tres_couru, _epreuve(db_session, f"P-herry-{i}"), "1")
    db_session.commit()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr")

    assert [a.nom for a, _ in resultats] == ["HERRY", "HERRMANN"]


def test_search_by_relevance_respecte_club_only(db_session):
    athlete_repository.get_or_create(
        db_session, nom="HERRMANN", prenom="Mathieu", club="Triathlon Club Nantais"
    )
    athlete_repository.get_or_create(
        db_session, nom="HERRY", prenom="Yves", club="Un Autre Club"
    )
    db_session.flush()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr", club_only=True)

    assert [a.nom for a, _ in resultats] == ["HERRMANN"]


def test_search_by_relevance_respecte_la_limite(db_session):
    for i in range(3):
        athlete_repository.get_or_create(db_session, nom=f"HERR{i}", prenom="A")
    db_session.flush()

    resultats = athlete_repository.search_by_relevance(db_session, term="herr", limit=2)

    assert len(resultats) == 2


# ── club_roster (issue #581) ───────────────────────────────────────────────


def _course(db_session, nom, event_type="triathlon-m"):
    return course_repository.get_or_create(
        db_session, name=nom, event_date=date(2026, 5, 16), event_type=event_type
    )


def _part(db_session, athlete, course, bib, **kwargs):
    kwargs.setdefault("club", "TCN")
    kwargs.setdefault("status", "finisher")
    return participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=bib, **kwargs
    )


def test_club_roster_trie_par_volume_puis_podiums_puis_nom(db_session):
    alice = athlete_repository.get_or_create(db_session, nom="ALICE", prenom="A", club="TCN")
    bob = athlete_repository.get_or_create(db_session, nom="BOB", prenom="B", club="TCN")
    c1 = _course(db_session, "C1")
    c2 = _course(db_session, "C2")
    _part(db_session, alice, c1, "1", rank_overall=1)
    _part(db_session, alice, c2, "2")
    _part(db_session, bob, c1, "3", rank_overall=2)
    db_session.flush()

    lignes = athlete_repository.club_roster(db_session)

    assert [a.nom for a, *_ in lignes] == ["ALICE", "BOB"]
    alice_row = lignes[0]
    assert alice_row[1:] == (2, 1, 1, 0, 0)  # count, podiums, overall, gender, category


def test_club_roster_ventile_les_podiums_par_portee_independamment(db_session):
    # Une seule participation, podium sur les trois portées à la fois
    # (cas mesuré Hadrien à Mesquer, #488) : les trois compteurs de portée
    # s'incrémentent chacun, `podiums` (dédupliqué) ne compte qu'une fois.
    ath = athlete_repository.get_or_create(db_session, nom="MULTI", prenom="M", club="TCN")
    course = _course(db_session, "C")
    _part(db_session, ath, course, "1", rank_overall=2, rank_category=1, rank_gender=2)
    db_session.flush()

    (a, count, podiums, po, pg, pc) = athlete_repository.club_roster(db_session)[0]
    assert (count, podiums, po, pg, pc) == (1, 1, 1, 1, 1)


def test_club_roster_exclut_hors_club(db_session):
    exterieur = athlete_repository.get_or_create(db_session, nom="DEHORS", prenom="D", club="Un Autre Club")
    course = _course(db_session, "C")
    _part(db_session, exterieur, course, "1", club="Un Autre Club")
    db_session.flush()

    assert athlete_repository.club_roster(db_session) == []


def test_club_roster_respecte_federal_only(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="TRAILEUR", prenom="T", club="TCN")
    course = _course(db_session, "Trail", event_type="trail")
    _part(db_session, ath, course, "1")
    db_session.flush()

    assert athlete_repository.club_roster(db_session, federal_only=False) != []
    assert athlete_repository.club_roster(db_session, federal_only=True) == []


def test_club_roster_plafonne_a_limit(db_session):
    course = _course(db_session, "C")
    for i in range(3):
        ath = athlete_repository.get_or_create(db_session, nom=f"N{i}", prenom="P", club="TCN")
        _part(db_session, ath, course, str(i))
    db_session.flush()

    assert len(athlete_repository.club_roster(db_session, limit=2)) == 2


# ── club_composition (issue #642) ───────────────────────────────────────────


def test_club_composition_compte_un_genre_par_athlete(db_session):
    alice = athlete_repository.get_or_create(
        db_session, nom="ALICE", prenom="A", gender="F", club="TCN"
    )
    bob = athlete_repository.get_or_create(
        db_session, nom="BOB", prenom="B", gender="M", club="TCN"
    )
    course = _course(db_session, "C")
    _part(db_session, alice, course, "1")
    _part(db_session, bob, course, "2")
    db_session.flush()

    lignes = athlete_repository.club_composition(db_session)

    assert sorted(lignes) == sorted([("F", None), ("M", None)])


def test_club_composition_prend_la_categorie_de_la_derniere_participation(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="ALICE", prenom="A", club="TCN")
    ancienne = course_repository.get_or_create(
        db_session, name="Ancienne", event_date=date(2024, 5, 16), event_type="triathlon-m"
    )
    recente = course_repository.get_or_create(
        db_session, name="Récente", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    _part(db_session, ath, ancienne, "1", category="V1")
    _part(db_session, ath, recente, "2", category="V2")
    db_session.flush()

    lignes = athlete_repository.club_composition(db_session)

    assert lignes == [(ath.gender, "V2")]


def test_club_composition_exclut_hors_club(db_session):
    exterieur = athlete_repository.get_or_create(
        db_session, nom="DEHORS", prenom="D", club="Un Autre Club"
    )
    course = _course(db_session, "C")
    _part(db_session, exterieur, course, "1", club="Un Autre Club")
    db_session.flush()

    assert athlete_repository.club_composition(db_session) == []


def test_club_composition_respecte_federal_only(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="TRAILEUR", prenom="T", club="TCN")
    course = _course(db_session, "Trail", event_type="trail")
    _part(db_session, ath, course, "1")
    db_session.flush()

    assert athlete_repository.club_composition(db_session, federal_only=False) != []
    assert athlete_repository.club_composition(db_session, federal_only=True) == []


# ── club_rank (issue #641) ──────────────────────────────────────────────────


def test_club_rank_renvoie_le_rang_et_le_total_au_dela_de_laperçu(db_session):
    course = _course(db_session, "C")
    alice = athlete_repository.get_or_create(db_session, nom="ALICE", prenom="A", club="TCN")
    bob = athlete_repository.get_or_create(db_session, nom="BOB", prenom="B", club="TCN")
    carl = athlete_repository.get_or_create(db_session, nom="CARL", prenom="C", club="TCN")
    for i in range(3):
        _part(db_session, alice, course, f"a{i}")
    for i in range(2):
        _part(db_session, bob, course, f"b{i}")
    _part(db_session, carl, course, "c0")
    db_session.flush()

    assert athlete_repository.club_rank(db_session, bob.id) == (2, 3)


def test_club_rank_renvoie_none_hors_roster(db_session):
    alice = athlete_repository.get_or_create(db_session, nom="ALICE", prenom="A", club="TCN")

    assert athlete_repository.club_rank(db_session, alice.id) is None


def test_club_rank_respecte_federal_only(db_session):
    ath = athlete_repository.get_or_create(db_session, nom="TRAILEUR", prenom="T", club="TCN")
    course = _course(db_session, "Trail", event_type="trail")
    _part(db_session, ath, course, "1")
    db_session.flush()

    assert athlete_repository.club_rank(db_session, ath.id, federal_only=False) == (1, 1)
    assert athlete_repository.club_rank(db_session, ath.id, federal_only=True) is None


# ── get_by_identities_batch (#706) ──────────────────────────────────────────


def test_get_by_identities_batch_retrouve_toutes_les_paires_en_une_requete(db_session):
    a1 = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    a2 = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul")
    db_session.flush()

    found = athlete_repository.get_by_identities_batch(
        db_session, [("Dupont", "Jean"), ("MARTIN", "PAUL")]
    )

    assert found == {
        ("dupont", "jean"): a1,
        ("martin", "paul"): a2,
    }


def test_get_by_identities_batch_omet_les_paires_absentes(db_session):
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    db_session.flush()

    found = athlete_repository.get_by_identities_batch(
        db_session, [("Dupont", "Jean"), ("Inconnu", "Personne")]
    )

    assert list(found.keys()) == [("dupont", "jean")]


def test_get_by_identities_batch_filtre_sur_birth_date_none(db_session):
    """La résolution d'import ne connaît jamais de date de naissance (#706,
    research.md) : un homonyme avec `birth_date` renseignée ne doit pas
    matcher."""
    athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", birth_date=date(1985, 6, 2)
    )
    db_session.flush()

    found = athlete_repository.get_by_identities_batch(db_session, [("Martin", "Paul")])

    assert found == {}


def test_get_by_identities_batch_paire_vide_ne_requete_rien(db_session):
    assert athlete_repository.get_by_identities_batch(db_session, []) == {}


# ── create_batch (#706) ──────────────────────────────────────────────────────


def test_create_batch_cree_toutes_les_fiches_et_leur_id_est_peuple(db_session):
    created = athlete_repository.create_batch(
        db_session,
        [
            {"nom": "NOUVEAU", "prenom": "Nino", "club": "TCN"},
            {"nom": "AUTRE", "prenom": "Alice", "gender": "F"},
        ],
    )

    assert [a.nom for a in created] == ["NOUVEAU", "AUTRE"]
    assert all(a.id is not None for a in created)
    assert created[0].club == "TCN"
    assert created[1].gender == "F"


def test_create_batch_liste_vide_ne_cree_rien(db_session):
    assert athlete_repository.create_batch(db_session, []) == []

"""Un rang non global côté source renumérote `rank_overall` par temps (#757, #785).

Mesuré sur RaceResult (3 façades) : certaines épreuves publient leur champ de
rang (`AUTORANK`) **par groupe d'affichage** — le genre, le plus souvent — et
non pour l'épreuve entière. Deux finishers de groupes différents peuvent donc
partager le même `rank_overall` sans qu'aucun ne soit réellement premier :
constaté en direct sur Embrunman, deux vainqueurs de rang 1, temps 09:17:39 et
10:28:19 (celui-ci pourtant classé derrière un homme parti dans un groupe
distinct). `services/quality.py::_rank_anomalies` le relève en
`duplicate_rank`.

Le fix renumérote `rank_overall` en 1..N par temps croissant, au même point
que la renumérotation solo/relais (#672) — mais sur un critère différent : le
rang source ne peut pas servir de tri (deux ordres indépendants y sont
mélangés), contrairement au rang combiné du cas #672 où l'ordre relatif reste
correct.
"""
from datetime import date

from app.core.config import Settings
from app.repositories import course_repository, participation_repository
from app.scrapers.base import STATUS_DSQ, STATUS_FINISHER, ScrapedResult
from app.services import import_service

URL = "https://my.raceresult.com/350635/results?contest=1"
NOM = "Embrunman - {EN:Embrunman|FR:Embruman}"
JOUR = date(2025, 8, 15)
TYPE = "triathlon-xl"


def _settings() -> Settings:
    return Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)


def _result(
    bib: str, rank_overall: int, total_time: str, *,
    is_relay: bool = False, status: str = STATUS_FINISHER, provider: str = "raceresult",
) -> ScrapedResult:
    return ScrapedResult(
        source_url=URL,
        provider=provider,
        athlete_name=f"NOM-{bib}",
        athlete_firstname="Jean",
        bib_number=bib,
        event_name=NOM,
        event_date=JOUR,
        event_type=TYPE,
        is_relay=is_relay,
        rank_overall=rank_overall,
        total_time=total_time,
        status=status,
    )


def test_deux_groupes_avec_rang_1_partage_sont_renumerotes_par_temps(db_session, patch_scraper):
    """Carte exacte mesurée sur Embrunman : deux « rang 1 » (un par genre),
    temps 09:17:39 et 10:28:19 — le temps le plus rapide doit obtenir le
    rang 1 une fois fusionné, peu importe le rang porté par la source."""
    patch_scraper(
        [
            _result("104", 1, "09:17:39"),  # rang source 1 (groupe hommes)
            _result("7", 1, "10:28:19"),    # rang source 1 (groupe femmes)
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    assert course is not None
    ranks = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }
    assert ranks == {"104": 1, "7": 2}
    assert course.is_reliable is True
    assert course.quality_issues == {}


def test_quatre_lignes_deux_groupes_reordonnees_par_temps_croissant(db_session, patch_scraper):
    """Généralise à 2 groupes de 2 : le classement fusionné doit suivre le
    temps du plus rapide au plus lent, indépendamment du rang source."""
    patch_scraper(
        [
            _result("F1", 1, "10:00:00"),
            _result("F2", 2, "11:00:00"),
            _result("H1", 1, "09:00:00"),
            _result("H2", 2, "09:30:00"),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    ranks = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }
    assert ranks == {"H1": 1, "H2": 2, "F1": 3, "F2": 4}


def test_sans_doublon_le_rang_source_est_conserve(db_session, patch_scraper):
    """Garde-fou : un rang déjà unique dans ce lot n'est pas retouché — rien
    n'indique qu'il est scindé par groupe d'affichage, y toucher serait sans
    fondement et pourrait même désaccorder un rang authentiquement global
    d'un temps mal formé ou incomparable (chronométrage manuel, ex æquo
    officiel déjà tranché par la source)."""
    patch_scraper(
        [
            _result("1", 1, "09:00:00"),
            _result("2", 2, "10:00:00"),
            _result("3", 3, "08:00:00"),  # rang 3 alors que le temps est le plus rapide
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    ranks = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }
    # Rang source conservé tel quel : aucun doublon dans ce lot, rien à corriger.
    assert ranks == {"1": 1, "2": 2, "3": 3}


def test_temps_illisible_part_en_fin_de_classement_pas_en_tete(db_session, patch_scraper):
    """Revue de #785 : un temps vide/illisible ne doit pas hériter du rang 1
    par accident de `to_seconds` non strict (0 par défaut, pensé pour un
    cumul, pas un tri) — il part en fin de classement, comme un temps
    manifestement pire que tout temps lisible."""
    patch_scraper(
        [
            _result("rapide", 1, "09:00:00"),
            _result("lent", 1, "10:00:00"),
            _result("illisible", 1, ""),  # temps vide, même rang doublonné
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    ranks = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }
    assert ranks == {"rapide": 1, "lent": 2, "illisible": 3}


def test_non_finisher_avec_rang_numerique_nest_ni_renumerote_ni_pris_en_compte(
    db_session, patch_scraper,
):
    """Revue de #785 : un DSQ qui porterait malgré tout un `rank_overall`
    numérique (défaut d'un autre scraper, jamais RaceResult qui met `None`)
    ne doit ni participer à la détection de doublon, ni être renumeroté —
    seuls les finishers sont concernés, comme
    `services/quality.py::_rank_anomalies`."""
    patch_scraper(
        [
            _result("104", 1, "09:17:39"),
            _result("7", 1, "10:28:19"),
            _result("dsq", 1, "", status=STATUS_DSQ),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    ranks = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }
    assert ranks["104"] == 1
    assert ranks["7"] == 2
    assert ranks["dsq"] == 1  # rang d'origine du DSQ inchangé, jamais examiné


def test_doublon_de_rang_et_scission_relais_dans_le_meme_lot(db_session, patch_scraper):
    """Revue de #785 : quand une épreuve scinde par `is_relay` (#672) **et**
    porte un doublon de rang par groupe d'affichage dans le sous-groupe solo,
    les deux renumérotations doivent composer sans que l'une masque l'autre —
    la renumérotation par temps (#785) doit s'appliquer **avant** la
    compression du rang combiné (#672), sans quoi le doublon serait
    « uniquifié » par un simple tri stable avant que #785 ait pu le détecter."""
    patch_scraper(
        [
            # F1 (le plus lent) arrive **avant** H1 dans le scrape : un simple
            # tri stable sur le rang source (déjà doublonné 1,1) les laisserait
            # dans cet ordre d'arrivée — F1 récupérerait le rang 1 à tort.
            _result("F1", 1, "10:00:00", is_relay=False),   # doublon rang 1, solo
            _result("H1", 1, "09:00:00", is_relay=False),   # doublon rang 1, solo
            _result("R1", 597, "01:59:00", is_relay=True),  # rang combiné, relais
            _result("R2", 598, "01:58:00", is_relay=True),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    solo = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, False)
    relais = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, True)
    ranks_solo = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, solo.id)
    }
    ranks_relais = {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, relais.id)
    }
    # Solo : doublon résolu par temps (H1 plus rapide → 1).
    assert ranks_solo == {"H1": 1, "F1": 2}
    # Relais : rang combiné compressé en 1..N, ordre d'origine préservé.
    assert ranks_relais == {"R1": 1, "R2": 2}



def _ranks(db_session, is_relay: bool = False) -> dict[str, int | None]:
    course = course_repository.get_by_identity(db_session, NOM, JOUR, TYPE, is_relay)
    return {
        p.bib_number: p.rank_overall
        for p in participation_repository.list_for_course(db_session, course.id)
    }


# --- Opt-in par fournisseur, statut effectif (#940) ---------------------------


def test_finishers_au_statut_vide_sont_renumerotes_chez_un_fournisseur_par_groupe(
    db_session, patch_scraper
):
    """Le statut « finisher » n'est dérivé qu'à la persistance : un statut vide
    avec un temps lisible est un finisher pour la renumérotation (#940)."""
    patch_scraper(
        [
            _result("A", 1, "01:00:00", status=""),
            _result("B", 1, "01:05:00", status=""),
            _result("C", 2, "01:10:00", status=""),
            _result("D", 2, "01:02:00", status=""),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    assert _ranks(db_session) == {"A": 1, "D": 2, "B": 3, "C": 4}


def test_statut_vide_sans_temps_reste_hors_du_lot_renumerote(db_session, patch_scraper):
    """Sans temps, le statut effectif est DNF : la ligne n'entre pas dans le tri."""
    patch_scraper(
        [
            _result("A", 1, "01:05:00", status=""),
            _result("B", 1, "01:00:00", status=""),
            _result("C", 1, "", status=""),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    ranks = _ranks(db_session)
    assert (ranks["B"], ranks["A"]) == (1, 2)
    assert ranks["C"] == 1


def test_relais_runnerbreizh_aux_rangs_partages_n_est_jamais_renumerote():
    """RunnerBreizh publie une ligne par équipier, rang et temps partagés
    (`docs/scrapers/runnerbreizh.md`) : 1,1,2,2 reste 1,1,2,2 (#940)."""
    results = [
        _result(f"E{index}", rank, temps, status="", is_relay=True, provider="runnerbreizh")
        for index, (rank, temps) in enumerate(
            [(1, "01:00:00"), (1, "01:00:00"), (2, "01:04:00"), (2, "01:04:00")]
        )
    ]

    import_service._renumber_duplicate_ranks(results)

    assert [r.rank_overall for r in results] == [1, 1, 2, 2]


def test_vrais_ex_aequo_d_un_fournisseur_non_declare_sont_preserves(
    db_session, patch_scraper
):
    """Un doublon 1,2,2,4 chez un fournisseur qui classe l'épreuve entière est
    une égalité, pas un rang par groupe : jamais renuméroté, même finisher
    explicite et temps différents (pénalité, temps officiel) (#940)."""
    patch_scraper(
        [
            _result("A", 1, "01:00:00", provider="sporthive"),
            _result("B", 2, "01:06:00", provider="sporthive"),
            _result("C", 2, "01:05:00", provider="sporthive"),
            _result("D", 4, "01:07:00", provider="sporthive"),
        ]
    )
    import_service.import_event(db_session, URL, _settings())

    assert _ranks(db_session) == {"A": 1, "B": 2, "C": 2, "D": 4}


def test_seul_raceresult_declare_un_rang_par_groupe():
    from app.scrapers import registry

    assert [p.name for p in registry.PROVIDERS if p.ranks_per_group] == ["raceresult"]

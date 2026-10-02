"""Athlete identity at import: equivalent spellings, swapped and concatenated
names land on the existing record (#907, #908, epic #1146)."""
from app.models.athlete import Athlete
from app.repositories import athlete_repository
from app.services import import_service
from tests.test_services.test_import_service import URL, _expire_cache, _result, _settings


def _athletes(db_session) -> list[tuple[str, str]]:
    return [(a.nom, a.prenom) for a in db_session.query(Athlete).order_by(Athlete.id)]


def _import(db_session, patch_scraper, rows) -> dict:
    patch_scraper(rows)
    out = import_service.import_event(db_session, URL, _settings())
    db_session.flush()
    return out


def _carrier(db_session, bib: str) -> Athlete:
    from app.models.participation import Participation

    return db_session.query(Participation).filter_by(bib_number=bib).one().athlete


def _seed(db_session, *identities: tuple[str, str]) -> list[Athlete]:
    """Commitées : un import qui échoue fait un rollback, et des fiches seulement
    flushées disparaîtraient avec lui, ids réattribués compris."""
    athletes = [athlete_repository.get_or_create(db_session, nom=nom, prenom=prenom) for nom, prenom in identities]
    db_session.commit()
    return athletes


def test_equivalent_spellings_join_the_existing_record(db_session, patch_scraper):
    leo, fabien, marie = _seed(
        db_session, ("LETORT", "Léo"), ("LE GLOANIC", "Fabien"), ("L'APPARTIEN", "Marie")
    )

    _import(db_session, patch_scraper, [
        _result("1", "LETORT", "Leo"), _result("2", "LEGLOANIC", "Fabien"), _result("3", "L APPARTIEN", "Marie"),
    ])

    assert [_carrier(db_session, bib).id for bib in ("1", "2", "3")] == [leo.id, fabien.id, marie.id]
    assert len(_athletes(db_session)) == 3


def test_a_swapped_name_joins_the_existing_record(db_session, patch_scraper):
    [moriarty] = _seed(db_session, ("ALEXANDER", "Moriarty"))

    _import(db_session, patch_scraper, [_result("1", "MORIARTY", "Alexander")])

    assert _carrier(db_session, "1").id == moriarty.id
    assert len(_athletes(db_session)) == 1


def test_a_concatenated_name_joins_the_split_record(db_session, patch_scraper):
    [jean] = _seed(db_session, ("DUPONT", "Jean"))

    _import(db_session, patch_scraper, [_result("1", "DUPONT JEAN", "")])

    assert _carrier(db_session, "1").id == jean.id
    assert len(_athletes(db_session)) == 1


def test_a_split_name_joins_the_concatenated_record(db_session, patch_scraper):
    [concatenated] = _seed(db_session, ("DUPONT JEAN", ""))

    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean")])

    assert _carrier(db_session, "1").id == concatenated.id


def test_numbered_teams_stay_apart(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "CIC 7", ""), _result("2", "CIC 9", "")])

    assert _carrier(db_session, "1").id != _carrier(db_session, "2").id


def test_the_direct_identity_wins_over_the_swap(db_session, patch_scraper):
    """« MARTIN Thomas » et « THOMAS Martin » peuvent être deux personnes."""
    martin_thomas, thomas_martin = _seed(db_session, ("MARTIN", "Thomas"), ("THOMAS", "Martin"))

    _import(db_session, patch_scraper, [_result("1", "THOMAS", "Martin")])

    assert _carrier(db_session, "1").id == thomas_martin.id != martin_thomas.id


def test_an_ambiguous_concatenation_creates_a_record_and_is_reported(db_session, patch_scraper):
    """« DUPONT JEAN » vaut « DUPONT Jean » comme « JEAN Dupont » : rien n'est deviné."""
    dupont_jean, jean_dupont = _seed(db_session, ("DUPONT", "Jean"), ("JEAN", "Dupont"))

    out = _import(db_session, patch_scraper, [_result("1", "DUPONT JEAN", "")])

    carrier = _carrier(db_session, "1")
    assert carrier.id not in {dupont_jean.id, jean_dupont.id}
    assert out["ambiguous_identities"] == [
        {"course_id": carrier.participations[0].course_id, "athlete_id": carrier.id,
         "candidate_ids": sorted([dupont_jean.id, jean_dupont.id])}
    ]


def test_a_bibless_row_without_identity_is_skipped(db_session, patch_scraper):
    out = _import(db_session, patch_scraper, [_result("", "-", ""), _result("2", "DURAND", "Paul")])

    assert out["imported"] == 1
    assert _athletes(db_session) == [("DURAND", "Paul")]


def test_a_row_without_identity_but_with_a_bib_is_found_again_on_rescrape(db_session, patch_scraper):
    _import(db_session, patch_scraper, [_result("1", "-", "")])
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("1", "-", "", total_time="02:01:00")])

    assert (out["imported"], out["updated"], out["reconciled"]) == (0, 1, 0)
    assert len(_athletes(db_session)) == 1


def test_a_dated_record_is_still_found(db_session, patch_scraper):
    """#900 : une date de naissance posée par un admin ne scinde plus la fiche."""
    from datetime import date

    [dated] = _seed(db_session, ("DUPONT", "Jean"))
    dated.birth_date = date(1990, 1, 1)
    db_session.commit()

    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean")])

    assert _carrier(db_session, "1").id == dated.id
    assert len(_athletes(db_session)) == 1


def test_a_fallback_never_joins_a_record_already_racing_with_another_bib(db_session, patch_scraper):
    """« THOMAS Martin » (dossard 1) et « MARTIN Thomas » (dossard 2) courent la
    même épreuve : ce sont deux personnes, l'inversion ne les fusionne pas."""
    [thomas_martin] = _seed(db_session, ("THOMAS", "Martin"))

    _import(db_session, patch_scraper, [_result("1", "THOMAS", "Martin"), _result("2", "MARTIN", "Thomas")])

    assert _carrier(db_session, "1").id == thomas_martin.id
    assert (_carrier(db_session, "2").nom, _carrier(db_session, "2").prenom) == ("MARTIN", "Thomas")


def test_two_fallback_rows_never_share_a_record(db_session, patch_scraper):
    [moriarty] = _seed(db_session, ("ALEXANDER", "Moriarty"))

    _import(db_session, patch_scraper, [
        _result("1", "MORIARTY", "Alexander"), _result("2", "ALEXANDER MORIARTY", ""),
    ])

    assert moriarty.id not in {_carrier(db_session, "1").id, _carrier(db_session, "2").id}


def test_a_rescrape_keeps_a_result_joined_by_fallback(db_session, patch_scraper):
    [moriarty] = _seed(db_session, ("ALEXANDER", "Moriarty"))
    _import(db_session, patch_scraper, [_result("1", "MORIARTY", "Alexander")])
    _expire_cache(db_session)

    out = _import(db_session, patch_scraper, [_result("1", "MORIARTY", "Alexander", total_time="02:01:00")])

    assert (out["updated"], out["reconciled"]) == (1, 0)
    assert _carrier(db_session, "1").id == moriarty.id


def test_a_first_name_alone_keeps_its_identity(db_session, patch_scraper):
    [jean] = _seed(db_session, ("DUPONT", "Jean"))

    _import(db_session, patch_scraper, [_result("", "", "Jean Dupont")])

    assert _athletes(db_session) == [("DUPONT", "Jean")]
    assert len(jean.participations) == 1


def test_a_relay_whose_teammates_share_one_identity_is_not_split(db_session, patch_scraper):
    from tests.test_services.test_import_service import _relay

    _import(db_session, patch_scraper, [_relay("1", "LE GLOANIC Fabien / LEGLOANIC Fabien", "")])

    (row,) = _carrier(db_session, "1").participations
    assert row.teammates == []


def test_a_merged_spelling_joins_the_kept_record_on_a_new_race(db_session, patch_scraper):
    """Q2 : la graphie absorbée par une fusion est mémorisée comme variante ; le
    rescrape de l'épreuve d'origine ne la recrée pas."""
    from datetime import date

    from app.repositories import user_repository
    from app.services import athlete_merge

    other, third = "https://www.klikego.com/resultats/event/456", "https://www.klikego.com/resultats/event/789"
    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean")])
    patch_scraper([_result("5", "DUPOMT", "Jean", event_name="Duathlon", event_date=date(2025, 4, 1), source_url=other)])
    import_service.import_event(db_session, other, _settings())
    kept = athlete_repository.get_by_identity_keys(db_session, "DUPONT", "Jean")
    typo = athlete_repository.get_by_identity_keys(db_session, "DUPOMT", "Jean")
    admin = user_repository.create(db_session, email="admin@exemple.fr")
    athlete_merge.merge_athletes(db_session, kept_id=kept.id, absorbed_id=typo.id, user_id=admin.id)
    db_session.commit()

    patch_scraper([_result("7", "DUPOMT", "Jean", event_name="Aquathlon", event_date=date(2025, 6, 1), source_url=third)])
    import_service.import_event(db_session, third, _settings())
    _expire_cache(db_session, other)
    patch_scraper([_result("5", "DUPOMT", "Jean", event_name="Duathlon", event_date=date(2025, 4, 1),
                           source_url=other, total_time="02:01:00")])
    out = import_service.import_event(db_session, other, _settings())
    db_session.flush()

    assert _carrier(db_session, "7").id == kept.id
    assert (_carrier(db_session, "5").id, out["reconciled"]) == (kept.id, 0)
    assert athlete_repository.get_by_identity_keys(db_session, "DUPOMT", "Jean") is None


def _merge_typo_into_dupont(db_session, patch_scraper):
    """« DUPOMT Jean » (autre épreuve) fusionné dans « DUPONT Jean » ; rend la fiche conservée."""
    from datetime import date

    from app.repositories import user_repository
    from app.services import athlete_merge

    other = "https://www.klikego.com/resultats/event/456"
    patch_scraper([_result("5", "DUPOMT", "Jean", event_name="Duathlon", event_date=date(2025, 4, 1), source_url=other)])
    import_service.import_event(db_session, other, _settings())
    patch_scraper([_result("6", "DUPONT", "Jean", event_name="Aquathlon", event_date=date(2025, 6, 1),
                           source_url="https://www.klikego.com/resultats/event/321")])
    import_service.import_event(db_session, "https://www.klikego.com/resultats/event/321", _settings())
    kept = athlete_repository.get_by_identity_keys(db_session, "DUPONT", "Jean")
    typo = athlete_repository.get_by_identity_keys(db_session, "DUPOMT", "Jean")
    admin = user_repository.create(db_session, email="admin@exemple.fr")
    athlete_merge.merge_athletes(db_session, kept_id=kept.id, absorbed_id=typo.id, user_id=admin.id)
    db_session.commit()
    return kept


def test_a_variant_never_puts_two_bibs_of_one_race_on_its_record(db_session, patch_scraper):
    """FR-008 vaut pour une variante comme pour un repli : « DUPONT Jean » (1) et
    « DUPOMT Jean » (2) sur une même épreuve sont deux personnes."""
    kept = _merge_typo_into_dupont(db_session, patch_scraper)

    _import(db_session, patch_scraper, [_result("1", "DUPONT", "Jean"), _result("2", "DUPOMT", "Jean")])

    assert _carrier(db_session, "1").id == kept.id
    assert (_carrier(db_session, "2").nom, _carrier(db_session, "2").homonym_rank) == ("DUPOMT", 0)


def test_a_relay_teammate_written_with_a_variant_joins_the_kept_record(db_session, patch_scraper):
    from tests.test_services.test_import_service import _relay

    kept = _merge_typo_into_dupont(db_session, patch_scraper)

    _import(db_session, patch_scraper, [_relay("1", "DUPOMT Jean / MARTIN Paul", "")])

    from app.models.participation import Participation

    relay = db_session.query(Participation).filter_by(bib_number="1").one()
    teammates = {link.athlete_id for link in relay.teammate_links}
    assert kept.id in teammates
    assert athlete_repository.get_by_identity_keys(db_session, "DUPOMT", "Jean") is None

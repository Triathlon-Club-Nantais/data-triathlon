from datetime import date
from types import SimpleNamespace

from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import participation_stats_service


def _participation(*, provider="raceresult", is_relay=False, splits=None, rank=1, total="01:00:00"):
    return SimpleNamespace(
        id=rank,
        course_id=1,
        course=SimpleNamespace(id=1, provider=provider),
        is_relay=is_relay,
        rank_overall=rank,
        total_time=total,
        splits=splits if splits is not None else {},
    )


def test_build_returns_none_when_course_is_not_eligible():
    participation = _participation(provider="t2area")
    assert participation_stats_service.build(None, participation) is None


def test_build_returns_none_for_a_relay():
    """FR-012 : la répartition des segments entre athlètes rend la lecture individuelle fausse."""
    participation = _participation(provider="raceresult", is_relay=True)
    assert participation_stats_service.build(None, participation) is None


def test_build_from_ranking_returns_the_three_blocks():
    participation = _participation(splits={"swim": "00:20:00", "bike": "00:30:00"})
    stats = participation_stats_service.build_from_ranking(participation, [participation])

    assert stats is not None
    assert stats.ranking_evolution is not None
    assert stats.comparison is not None
    assert stats.improvement is not None


def test_build_from_ranking_publishes_the_segment_list():
    """Sans elle, le front ne peut pas savoir quelles colonnes l'épreuve publie (FR-013)."""
    ranking = [
        _participation(rank=1, splits={"swim": "00:20:00", "t1": "00:02:00"}),
        _participation(rank=2, splits={"swim": "00:21:00", "bike": "01:00:00"}),
    ]

    stats = participation_stats_service.build_from_ranking(ranking[0], ranking)

    assert stats.segments == ["swim", "t1", "bike"]


def test_published_segments_keeps_publication_order():
    ranking = [
        _participation(rank=1, splits={"swim": "00:20:00", "t1": "00:02:00"}),
        _participation(rank=2, splits={"swim": "00:21:00", "t1": "00:02:30", "bike": "01:00:00"}),
    ]
    assert participation_stats_service.published_segments(ranking) == ["swim", "t1", "bike"]


def test_published_segments_invents_no_transition():
    """FR-013 : un duathlon sans T1/T2 chronométré n'ouvre pas de colonne vide."""
    ranking = [_participation(rank=1, splits={"course1": "00:15:00", "bike": "00:40:00", "course2": "00:18:00"})]
    assert participation_stats_service.published_segments(ranking) == ["course1", "bike", "course2"]


def test_published_segments_ignores_missing_splits():
    ranking = [
        _participation(rank=1, splits=None),
        _participation(rank=2, splits={"run": "00:40:00"}),
    ]
    assert participation_stats_service.published_segments(ranking) == ["run"]


def _three_row_ranking():
    """Classement calibré : le 25e met exactement 1,5× le 1er et 1,2× le 10e, partout."""
    return [
        _participation(rank=1, total="01:20:00", splits={"swim": "00:20:00", "bike": "01:00:00"}),
        _participation(rank=10, total="01:40:00", splits={"swim": "00:25:00", "bike": "01:15:00"}),
        _participation(rank=25, total="02:00:00", splits={"swim": "00:30:00", "bike": "01:30:00"}),
    ]


def _comparison(ranking, athlete_rank):
    athlete = next(row for row in ranking if row.rank_overall == athlete_rank)
    return {row.rank: row for row in participation_stats_service.build_from_ranking(athlete, ranking).comparison}


def test_comparison_expresses_athlete_time_as_a_percentage_of_the_reference():
    ranking = _three_row_ranking()

    rows = _comparison(ranking, 25)

    assert rows[1].percentages == {"swim": 150.0, "bike": 150.0, "total": 150.0}
    assert rows[10].percentages == {"swim": 120.0, "bike": 120.0, "total": 120.0}


def test_comparison_labels_the_reference_positions_in_french():
    rows = _comparison(_three_row_ranking(), 25)

    assert rows[1].position_label == "1er"
    assert rows[10].position_label == "10e"
    assert rows[25].position_label == "25e"


def test_comparison_compares_the_athlete_to_itself_at_one_hundred_percent():
    rows = _comparison(_three_row_ranking(), 25)

    assert rows[25].percentages == {"swim": 100.0, "bike": 100.0, "total": 100.0}


def test_comparison_omits_reference_positions_the_field_does_not_reach():
    """FR-014 : une ligne vide serait lue comme une performance, pas comme une absence."""
    rows = _comparison(_three_row_ranking(), 25)

    assert set(rows) == {1, 10, 25}


def test_comparison_invents_no_percentage_when_a_split_is_missing():
    """FR-007 : un segment non publié n'a pas de pourcentage, il n'en a pas zéro."""
    ranking = [
        _participation(rank=1, total="01:20:00", splits={"swim": "00:20:00", "bike": "01:00:00"}),
        _participation(rank=10, total="01:40:00", splits={"bike": "01:15:00"}),
    ]

    rows = _comparison(ranking, 10)

    assert "swim" not in rows[1].percentages
    assert rows[1].percentages == {"bike": 125.0, "total": 125.0}


def test_comparison_exposes_raw_seconds_alongside_percentages():
    """US4 (#466) : l'écart en secondes brutes est déjà calculé, jamais exposé."""
    rows = _comparison(_three_row_ranking(), 25)

    assert rows[1].mine_seconds == {"swim": 1800, "bike": 5400, "total": 7200}
    assert rows[1].theirs_seconds == {"swim": 1200, "bike": 3600, "total": 4800}


def test_comparison_raw_seconds_share_the_same_keys_as_percentages():
    """Même garde qu'un segment manquant côté pourcentages (FR-007) : pas de zéro inventé."""
    ranking = [
        _participation(rank=1, total="01:20:00", splits={"swim": "00:20:00", "bike": "01:00:00"}),
        _participation(rank=10, total="01:40:00", splits={"bike": "01:15:00"}),
    ]

    rows = _comparison(ranking, 10)

    assert "swim" not in rows[1].mine_seconds
    assert "swim" not in rows[1].theirs_seconds
    assert rows[1].mine_seconds == {"bike": 4500, "total": 6000}
    assert rows[1].theirs_seconds == {"bike": 3600, "total": 4800}


def _tight_ranking():
    """Peloton serré à l'arrivée : quelques secondes gagnées changent le rang."""
    return [
        _participation(rank=1, total="01:38:20", splits={"swim": "00:20:00", "bike": "00:58:20"}),
        _participation(rank=2, total="01:38:40", splits={"swim": "00:20:00", "bike": "00:58:40"}),
        _participation(rank=3, total="01:39:00", splits={"swim": "00:20:00", "bike": "00:59:00"}),
        _participation(rank=4, total="01:39:20", splits={"swim": "00:20:00", "bike": "00:59:20"}),
        _participation(rank=5, total="01:40:00", splits={"swim": "00:20:00", "bike": "01:00:00"}),
    ]


def _improvement(ranking, athlete_rank):
    athlete = next(row for row in ranking if row.rank_overall == athlete_rank)
    rows = participation_stats_service.build_from_ranking(athlete, ranking).improvement
    return {row.segment: row.gains for row in rows}


def test_improvement_counts_the_scratch_places_a_faster_segment_would_win():
    gains = _improvement(_tight_ranking(), 5)["bike"]

    assert gains == {"0.5": 0, "1": 0, "2": 2, "5": 4, "10": 4, "25": 4}


def test_improvement_covers_the_six_percentages():
    gains = _improvement(_tight_ranking(), 5)["bike"]

    assert list(gains) == ["0.5", "1", "2", "5", "10", "25"]


def test_improvement_has_one_row_per_published_segment():
    rows = _improvement(_tight_ranking(), 5)

    assert list(rows) == ["swim", "bike"]


def test_improvement_never_reports_a_negative_gain():
    """Le 1er ne peut rien gagner : zéro place, jamais une place négative."""
    gains = _improvement(_tight_ranking(), 1)["bike"]

    assert set(gains.values()) == {0}


def test_improvement_skips_a_segment_the_athlete_did_not_publish():
    ranking = [
        _participation(rank=1, total="01:38:20", splits={"swim": "00:20:00", "bike": "00:58:20"}),
        _participation(rank=2, total="01:40:00", splits={"bike": "01:00:00"}),
    ]

    rows = _improvement(ranking, 2)

    assert list(rows) == ["bike"]


def _evolution_ranking():
    """Trois coureurs qui se doublent : C sort premier de l'eau, A gagne au cumul."""
    return [
        _participation(rank=1, total="01:20:00", splits={"swim": "00:20:00", "bike": "01:00:00"}),
        _participation(rank=2, total="01:22:00", splits={"swim": "00:25:00", "bike": "00:57:00"}),
        _participation(rank=3, total="01:28:00", splits={"swim": "00:18:00", "bike": "01:10:00"}),
    ]


def _evolution(ranking, athlete_rank):
    athlete = next(row for row in ranking if row.rank_overall == athlete_rank)
    steps = participation_stats_service.build_from_ranking(athlete, ranking).ranking_evolution
    return {step.segment: step for step in steps}


def test_ranking_evolution_tracks_the_cumulative_scratch_position():
    steps = _evolution(_evolution_ranking(), 1)

    assert steps["swim"].scratch_position == 2
    assert steps["bike"].scratch_position == 1


def test_ranking_evolution_ranks_each_segment_in_isolation():
    """Le 2e au général est le meilleur sur le vélo pris seul : c'est ce que la barre montre."""
    steps = _evolution(_evolution_ranking(), 2)

    assert steps["bike"].segment_position == 1
    assert steps["bike"].scratch_position == 2


def test_ranking_evolution_has_one_step_per_published_segment():
    steps = _evolution(_evolution_ranking(), 1)

    assert list(steps) == ["swim", "bike"]


def test_ranking_evolution_ends_on_the_official_rank():
    """SC-005 : le dernier point est le classement de l'épreuve, pas une somme de splits."""
    ranking = [
        # Le 1er officiel a les pires splits publiés : la somme et le rang divergent.
        _participation(rank=1, total="01:20:00", splits={"swim": "00:40:00", "bike": "02:00:00"}),
        _participation(rank=2, total="01:22:00", splits={"swim": "00:20:00", "bike": "01:00:00"}),
    ]

    steps = _evolution(ranking, 1)

    assert steps["bike"].scratch_position == 1


def test_comparison_skips_a_reference_without_a_usable_total():
    ranking = [
        _participation(rank=1, total=None, splits={"swim": "00:20:00"}),
        _participation(rank=10, total="01:40:00", splits={"swim": "00:25:00"}),
    ]

    rows = _comparison(ranking, 10)

    assert "total" not in rows[1].percentages
    assert rows[1].percentages == {"swim": 125.0}


# ── Assemblage bout en bout : repository → service → forme de sortie ──────────


def _seed_course(db, provider="raceresult"):
    # `source_url` non vide : depuis #279 le fournisseur d'une épreuve se lit sur
    # sa source active, et sans URL aucune source n'est créée — la course
    # naîtrait sans fournisseur, donc inéligible aux statistiques.
    course = course_repository.get_or_create(
        db,
        name="Tri de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        provider=provider,
        source_url=f"https://example.test/{provider}/nantes",
    )
    rows = []
    for index, (nom, total, swim, bike) in enumerate(
        [
            ("PREMIER", "01:20:00", "00:20:00", "01:00:00"),
            ("DEUXIEME", "01:30:00", "00:25:00", "01:05:00"),
            ("TROISIEME", "01:40:00", "00:30:00", "01:10:00"),
        ],
        start=1,
    ):
        athlete = athlete_repository.get_or_create(db, nom=nom, prenom="Jean", club="TCN")
        rows.append(
            participation_repository.create(
                db,
                athlete_id=athlete.id,
                course_id=course.id,
                bib_number=str(index),
                club="TCN",
                rank_overall=index,
                total_time=total,
                splits={"swim": swim, "bike": bike},
            )
        )
    db.flush()
    return course, rows


def test_build_assembles_every_block_from_the_database(db_session):
    _, rows = _seed_course(db_session)

    stats = participation_stats_service.build(db_session, rows[2])

    assert stats is not None
    assert stats.segments == ["swim", "bike"]
    assert [step.segment for step in stats.ranking_evolution] == ["swim", "bike"]
    assert [row.rank for row in stats.comparison] == [1]
    assert [row.segment for row in stats.improvement] == ["swim", "bike"]


def test_build_reads_the_whole_ranking_not_just_the_athlete(db_session):
    """Le service compare au classement complet : le 3e voit bien le 1er."""
    _, rows = _seed_course(db_session)

    stats = participation_stats_service.build(db_session, rows[2])

    assert stats.comparison[0].percentages["total"] == 125.0
    assert stats.ranking_evolution[-1].scratch_position == 3


def test_build_returns_none_from_the_database_for_an_excluded_provider(db_session):
    _, rows = _seed_course(db_session, provider="t2area")

    assert participation_stats_service.build(db_session, rows[0]) is None

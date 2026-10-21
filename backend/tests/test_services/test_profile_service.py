import pytest

from app.services import profile_service


@pytest.mark.parametrize(("history", "expected"), [
    ([], {"attended": 0, "pointed": 0, "absence_streak": 0}),
    ([False, False, True, False], {"attended": 1, "pointed": 4, "absence_streak": 2}),
    ([True, False], {"attended": 1, "pointed": 2, "absence_streak": 0}),
])
def test_attendance_summary(history, expected):
    assert profile_service.attendance_summary(history) == expected

import pytest

from app.services.public_page import InvalidLinkError, link_label, normalize_link


@pytest.mark.parametrize("url,label", [
    ("https://www.strava.com/athletes/123", "Strava"),
    ("https://connect.garmin.com/modern/profile/x", "Garmin Connect"),
    ("https://flow.polar.com/training/profiles/1", "Polar Flow"),
    ("https://www.suunto.com/x", "Suunto"),
    ("https://strava.com/a", "Strava"),
])
def test_accepted_links(url, label):
    assert normalize_link(f"  {url} ") == url
    assert link_label(url) == label


@pytest.mark.parametrize("url", [
    "http://strava.com/a",
    "https://strava.com.evil.example/a",
    "https://evil.example/?u=strava.com",
    "https://user@strava.com/a",
    "https://strava.com:8443/a",
    "javascript:alert(1)",
    "https://evilstrava.com/a",
    "https://strava.com/" + "a" * 200,
    "",
    "https://www.strava.com/a b",
])
def test_refused_links(url):
    with pytest.raises(InvalidLinkError):
        normalize_link(url)

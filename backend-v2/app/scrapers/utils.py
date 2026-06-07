"""
Shared utilities for all scrapers.
"""
import re
from datetime import date as date_t

_FR_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}


def parse_fr_date(text: str) -> "date_t | None":
    """Parse a French date string like '16 mai 2026' or '16–17 mai 2026'."""
    if not text:
        return None
    # Normalize accented chars and dashes
    normalized = (
        text.lower()
        .replace("é", "e").replace("è", "e").replace("û", "u")
        .replace("ô", "o").replace("â", "a").replace("î", "i")
        .replace("–", "-").replace("—", "-").replace("�", "-")
    )
    m = re.search(
        r"(\d{1,2})(?:[\s\-/]+\d{1,2})?\s+(" + "|".join(_FR_MONTHS) + r")\s+(\d{4})",
        normalized,
    )
    if m:
        month = _FR_MONTHS.get(m.group(2))
        if month:
            try:
                return date_t(int(m.group(3)), month, int(m.group(1)))
            except ValueError:
                pass
    return None


def normalize_time(raw: str) -> str:
    """
    Normalize a time string to HH:MM:SS format.

    Handles:
      "00h39'11"   → "00:39:11"
      "1:23:45"    → "01:23:45"
      "39:11"      → "00:39:11"
      "1h23'45\""  → "01:23:45"
      "1h23m45s"   → "01:23:45"
      ""           → ""
    """
    if not raw:
        return ""
    s = raw.strip().replace("\u2019", "'").replace("\u2018", "'")

    # Pattern: 00h39'11 or 1h23'45 or 1h23m45s
    m = re.match(r"(\d+)[hH](\d+)[m'\u2019](\d+)", s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:{int(m.group(3)):02d}"

    # Pattern: HH:MM:SS or H:MM:SS
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:{int(m.group(3)):02d}"

    # Pattern: MM:SS (no hours)
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        return f"00:{int(m.group(1)):02d}:{int(m.group(2)):02d}"

    # Pattern: 1h23m or 1h23 (no seconds)
    m = re.match(r"^(\d+)[hH](\d+)$", s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:00"

    return s  # return as-is if unrecognized


def normalize_rank(val) -> int | None:
    if val is None:
        return None
    try:
        return int(re.sub(r"[^\d]", "", str(val)))
    except (ValueError, TypeError):
        return None


def split_athlete_name(full: str) -> tuple[str, str]:
    """
    Wiclax / TimePulse convention: 'NOM Prénom' (surname first, uppercase).
    Returns (surname, firstname).
    """
    parts = full.strip().split("\n")[0].strip().split()
    if not parts:
        return "", ""
    # Detect if first token is all-uppercase → surname
    if parts[0].isupper():
        # Find where uppercase tokens end
        i = 0
        while i < len(parts) and parts[i].isupper():
            i += 1
        surname = " ".join(parts[:i])
        firstname = " ".join(parts[i:])
    else:
        surname = parts[-1]
        firstname = " ".join(parts[:-1])
    return surname, firstname

"""Épreuves jeunes, exclues de l'import (#881).

Un import d'événement ramène tous ses heats, y compris ceux des enfants, dont
les résultats nominatifs n'ont rien à faire dans l'outil (RGPD). Décision du
30/09 : on ignore tout ce qui va **jusqu'à Minime inclus** (Mini-poussin,
Poussin, Pupille, Benjamin, Minime, ou un heat « jeunes ») ; cadets et juniors
restent importés.

Deux signaux, un seul suffit : le nom du heat (mot jeune, tranche d'âge ou
année de naissance, #1255), qui qualifie toutes ses lignes,
et la catégorie de la ligne, pour un heat mixte ou muet.
"""
import re
from datetime import date

from app.core.text import deaccent

# Mot entier : « Minimoys » n'est pas une catégorie. `mini-poussin` se découpe en
# « mini » et « poussin », le second suffit.
_YOUTH_WORD_RE = re.compile(
    r"(?:mini)?poussin(?:e)?s?|pupilles?|benjamin(?:e)?s?|minimes?|jeunes?|kids?|avenir"
)
# « 6-9 ans », « 6/9 ans » : une tranche qui finit à Minime (15 ans) au plus (#1255).
_AGE_RANGE_RE = re.compile(r"\b\d{1,2}\s*[-/]\s*(\d{1,2})\s*ans\b")
_YOUTH_MAX_AGE = 15
# « nés 2014-2017 », « nées en 2016 » : la première année de naissance suffit.
_BIRTH_YEAR_RE = re.compile(r"\bnee?s?\s+(?:en\s+)?(\d{4})\b")
_WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")
# Codes FFTri/FFA : MP (ou MPO, Klikego, #1255), PO, PU, BE, MI, suivis ou non du sexe. `M1F` (master)
# ne s'y confond pas.
_YOUTH_CATEGORY_RE = re.compile(r"(?:MPO?|PO|PU|BE|MI)[HFMX]?")


def _has_youth_word(text: str) -> bool:
    text = (deaccent(text) or "").lower()
    if any(_YOUTH_WORD_RE.fullmatch(word) for word in _WORD_SPLIT_RE.split(text)):
        return True
    if any(int(top) <= _YOUTH_MAX_AGE for top in _AGE_RANGE_RE.findall(text)):
        return True
    youngest = date.today().year - _YOUTH_MAX_AGE
    return any(int(year) >= youngest for year in _BIRTH_YEAR_RE.findall(text))


def is_youth(event_name: str | None, category: str | None) -> bool:
    """Vrai si la ligne appartient à une épreuve jeune, à ne pas importer."""
    # « MI H » s'écrit aussi avec une espace : le code se compare sans elle.
    code = "".join((category or "").split()).upper()
    if _YOUTH_CATEGORY_RE.fullmatch(code):
        return True
    return _has_youth_word(event_name or "") or _has_youth_word(category or "")

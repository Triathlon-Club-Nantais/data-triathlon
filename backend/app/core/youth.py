"""Épreuves jeunes, exclues de l'import (#881).

Un import d'événement ramène tous ses heats, y compris ceux des enfants, dont
les résultats nominatifs n'ont rien à faire dans l'outil (RGPD). Décision du
30/09 : on ignore tout ce qui va **jusqu'à Minime inclus** (Mini-poussin,
Poussin, Pupille, Benjamin, Minime, ou un heat « jeunes ») ; cadets et juniors
restent importés.

Deux signaux, un seul suffit : le nom du heat, qui qualifie toutes ses lignes,
et la catégorie de la ligne, pour un heat mixte ou muet.
"""
import re

from app.core.text import deaccent

# Mot entier : « Minimoys » n'est pas une catégorie. `mini-poussin` se découpe en
# « mini » et « poussin », le second suffit.
_YOUTH_WORD_RE = re.compile(
    r"(?:mini)?poussin(?:e)?s?|pupilles?|benjamin(?:e)?s?|minimes?|jeunes?"
)
_WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")
# Codes FFTri/FFA : MP, PO, PU, BE, MI, suivis ou non du sexe. `M1F` (master)
# ne s'y confond pas.
_YOUTH_CATEGORY_RE = re.compile(r"(?:MP|PO|PU|BE|MI)[HFMX]?")


def _has_youth_word(text: str) -> bool:
    words = _WORD_SPLIT_RE.split((deaccent(text) or "").lower())
    return any(_YOUTH_WORD_RE.fullmatch(word) for word in words)


def is_youth(event_name: str | None, category: str | None) -> bool:
    """Vrai si la ligne appartient à une épreuve jeune, à ne pas importer."""
    # « MI H » s'écrit aussi avec une espace : le code se compare sans elle.
    code = "".join((category or "").split()).upper()
    if _YOUTH_CATEGORY_RE.fullmatch(code):
        return True
    return _has_youth_word(event_name or "") or _has_youth_word(category or "")

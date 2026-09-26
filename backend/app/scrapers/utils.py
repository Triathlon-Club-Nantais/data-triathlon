"""
Shared utilities for all scrapers.
"""
import re
import unicodedata
from datetime import date as date_t

from app.core.text import deaccent

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER

#: En-têtes par défaut de toute sortie HTTP d'un scraper. Onze modules en
#: portaient une copie identique au caractère près ; changer l'User-Agent
#: voulait dire onze éditions, et rien ne signalait celle qu'on oubliait.
#: Un fournisseur qui a besoin d'un `Referer` ou d'un `Accept` propre compose :
#: `{**DEFAULT_HEADERS, "Referer": …}`.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


def strip_accents(text: str) -> str:
    """Aplatit les accents : 'Été' → 'Ete'. Sept providers en portaient chacun
    une copie (table `str.maketrans` minuscules-only, ou ce même NFKD) ; une
    seule définition, casse préservée pour rester composable avec `.lower()`.
    """
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c))

_FR_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    # Formes abrégées telles qu'écrites par Klikego/Breizh Chrono ('12 avr. 2026').
    "janv": 1, "fevr": 2, "avr": 4, "juil": 7,
    "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Motifs de mois, les plus longs d'abord pour éviter qu'un abrégé (« juil »)
# ne capture avant le nom complet (« juillet »).
_FR_MONTHS_PATTERN = "|".join(sorted(_FR_MONTHS, key=len, reverse=True))


def parse_fr_date(text: str) -> "date_t | None":
    """Parse a French date string like '16 mai 2026', '16–17 mai 2026' or '12 avr. 2026'."""
    if not text:
        return None
    # Accents aplatis par la définition commune du module, tirets unifiés (#1107).
    normalized = (
        strip_accents(text.lower())
        .replace("–", "-").replace("—", "-").replace("�", "-")
    )
    # `\.?` tolère le point final des mois abrégés ('avr.', 'sept.').
    m = re.search(
        r"(\d{1,2})(?:[\s\-/]+\d{1,2})?\s+(" + _FR_MONTHS_PATTERN + r")\.?\s+(\d{4})",
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
      "00:12'15\"000"         → "00:12:15"
      "00:06:41 (00:06:45)"   → "00:06:41"
      "1:05:30.4"  → "01:05:30"
      "65:30"      → "01:05:30"
      ""           → ""
    """
    if not raw:
        return ""
    s = raw.strip().replace("\u2019", "'").replace("\u2018", "'")

    # Fraction de seconde tronquée (RaceResult `02:35:01,7`, Sporthive
    # `00:57:33.2510000`) : laissée, elle écartait un vrai chrono (#969).
    m = re.match(r"^(\d{1,3}:\d{2}(?::\d{2})?)[.,]\d+$", s)
    if m:
        s = m.group(1)

    # Pattern: 00h39'11 or 1h23'45 or 1h23m45s
    m = re.match(r"(\d+)[hH](\d+)[m'\u2019](\d+)", s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:{int(m.group(3)):02d}"

    # Klikego `00:12'15"000` : millièmes tronqués (#969).
    m = re.match(r"^(\d{1,2}):(\d{2})'(\d{2})(?:\"|'')\d*$", s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:{int(m.group(3)):02d}"

    # Sport Innovation `officiel (réel)` : l'officiel seul (#969).
    m = re.match(r"^(\d{1,2}:\d{2}:\d{2})\s*\(\d{1,2}:\d{2}:\d{2}\)$", s)
    if m:
        s = m.group(1)

    # Pattern: HH:MM:SS or H:MM:SS
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:{int(m.group(3)):02d}"

    # Pattern: MM:SS (no hours), minutes past the hour carried over (`65:30`).
    m = re.match(r"^(\d{1,3}):(\d{2})$", s)
    if m:
        hours, minutes = divmod(int(m.group(1)), 60)
        return f"{hours:02d}:{minutes:02d}:{int(m.group(2)):02d}"

    # Pattern: 1h23m or 1h23 (no seconds)
    m = re.match(r"^(\d+)[hH](\d+)$", s)
    if m:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:00"

    return s  # return as-is if unrecognized


#: `HH:MM:SS` ou `MM:SS`, ancré **en fin** de chaîne — un suffixe non lu
#: (`01:23:45.6`) ne doit pas être tronqué en silence, il doit sortir du motif.
#: L'ancrage n'est que final, et la lecture se fait au `search` : un *préfixe*
#: est avalé (`"total 01:23:45"` → 5025), comme le faisait `stats_service`.
#: Sans conséquence, tous les appelants normalisant en amont par `normalize_time`.
_TIME_RE = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})$")


def to_seconds(t: str | None, *, strict: bool = False) -> int | None:
    """Secondes d'un temps `HH:MM:SS` (ou `MM:SS`).

    Une seule définition pour les six copies qu'en portaient klikego, timepulse,
    wiclax, chronoweb, oktime et `stats_service`.

    `strict` porte la seule distinction réelle entre elles : à `False`, l'illisible
    vaut `0` — ce que veut un calcul de cumul, où l'absence de durée est un zéro ;
    à `True`, il vaut `None`, ce qui sépare « ce point ne porte pas de durée »
    (`00:00:00` → `0`) de « ce point est illisible » (`01:23:45.6` → `None`), une
    perte de donnée qui doit se journaliser.
    """
    match = _TIME_RE.search(t or "")
    if not match:
        return None if strict else 0
    return int(match.group(1) or 0) * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def fmt_seconds(s: int) -> str:
    """Secondes → `HH:MM:SS`."""
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def normalize_rank(val) -> int | None:
    if val is None:
        return None
    try:
        return int(re.sub(r"[^\d]", "", str(val)))
    except (ValueError, TypeError):
        return None


def split_athlete_name(full: str) -> tuple[str, str]:
    """Scinde un nom complet en (nom, prénom), quelle que soit la convention.

    Deux conventions coexistent chez les fournisseurs :
      - « NOM Prénom » (Wiclax, TimePulse) : bloc majuscule **en tête** ;
      - « Prénom NOM » (RaceResult) : bloc majuscule **en queue**.

    Le bloc majuscule est pris dans son intégralité des deux côtés, sinon un nom
    à particule (« Jean DE LA TOUR ») se réduirait à son dernier token. Sans
    aucun bloc majuscule, on retombe sur la convention « prénom(s) puis nom ».

    Limite assumée : un prénom entièrement en majuscules bascule à tort sur la
    convention « NOM Prénom ». Ainsi « JP ROUX » donne (« JP ROUX », « »)
    au lieu de (« ROUX », « JP »), et « JEAN MARTIN » donne (« JEAN MARTIN », « »).
    C'est une ambiguïté irréductible sans information supplémentaire — les deux
    lectures sont légitimes — et non un bug à corriger.

    La virgule, elle, lève l'ambiguïté : « NOM, Prénom » (`LFNAME` RaceResult)
    se coupe sur la **première** virgule, quelle que soit la casse (#906). Sans
    cette règle, « JUMEAUX, ADRIEN » restait nom entier sans prénom et
    « Courjon, Rose » sortait inversé, chacun doublonnant la fiche existante.
    """
    ligne = full.strip().split("\n")[0]
    if "," in ligne:
        gauche, droite = (" ".join(cote.split()) for cote in ligne.split(",", 1))
        if gauche and droite:
            return gauche, droite
        ligne = gauche or droite
    parts = ligne.strip().split()
    if not parts:
        return "", ""
    if parts[0].isupper():
        # « NOM Prénom » : le nom est le préfixe majuscule.
        i = 0
        while i < len(parts) and parts[i].isupper():
            i += 1
        return " ".join(parts[:i]), " ".join(parts[i:])
    if parts[-1].isupper():
        # « Prénom NOM » : le nom est le suffixe majuscule, particules incluses.
        i = len(parts)
        while i > 0 and parts[i - 1].isupper():
            i -= 1
        return " ".join(parts[i:]), " ".join(parts[:i])
    return parts[-1], " ".join(parts[:-1])


MIN_RELAY_TEAMMATES = 2
MAX_RELAY_TEAMMATES = 8


def split_relay_teammates(published: str) -> list[tuple[str, str]] | None:
    """`(nom, prénom)` of each named teammate of a relay line, in published order.

    All or nothing: `None` as soon as one teammate lacks an unambiguous name and
    first name. Rule and measured examples: `specs/20260925-130402-relay-name-split/
    contracts/relay-teammates-rule.md`. Callers only pass relay lines (#63).
    """
    # Le « . » isolé est un artefact klikego, jamais un nom.
    tokens = [token for token in published.split() if token.strip(".")]
    value = " ".join(tokens)
    if "/" not in value:
        return None
    names, firstnames = split_athlete_name(value)
    if "/" in names and "/" in firstnames:
        name_items = [item.strip() for item in names.split("/")]
        firstname_items = [item.strip() for item in firstnames.split("/")]
        if len(name_items) != len(firstname_items) or any(
            _joins_names(item.split()) for item in firstname_items
        ):
            return None
        teammates = list(zip(name_items, firstname_items, strict=True))
    else:
        teammates = [_relay_segment(segment) for segment in value.split("/")]
        if None in teammates:
            return None
    if not MIN_RELAY_TEAMMATES <= len(teammates) <= MAX_RELAY_TEAMMATES:
        return None
    if not all(_has_two_letters(part) for teammate in teammates for part in teammate):
        return None
    keys = {tuple(" ".join(deaccent(part).lower().split()) for part in t) for t in teammates}
    if len(keys) != len(teammates):
        return None
    return teammates


def _relay_segment(segment: str) -> tuple[str, str] | None:
    tokens = segment.split()
    if _joins_names(tokens):
        return None
    upper = [token.isupper() for token in tokens]
    if all(upper):
        # Tout en majuscules : lu « NOM PRÉNOM » (klikego, oktime, chronoplace) ;
        # au-delà de deux mots, la frontière entre nom et prénom est indécidable.
        return (tokens[0], tokens[1]) if len(tokens) == 2 else None
    if not any(upper):
        return None
    # Casse mixte : un seul bloc majuscule, en tête ou en queue, porte le nom.
    boundary = upper.index(not upper[0])
    if any(flag == upper[0] for flag in upper[boundary:]):
        return None
    head, tail = " ".join(tokens[:boundary]), " ".join(tokens[boundary:])
    return (head, tail) if upper[0] else (tail, head)


def _joins_names(tokens: list[str]) -> bool:
    return any(token in {"&", "+"} or token.lower() == "et" for token in tokens)


def _has_two_letters(part: str) -> bool:
    return sum(char.isalpha() for char in part) >= 2


# Jetons de statut bruts (FR/EN) → constante STATUS_*. Comparés sur le label
# normalisé (minuscule, sans accents ni ponctuation). Table volontairement
# conservatrice : à compléter à la lumière des payloads réels (cf. découverte
# par provider). Un label non listé → "" → l'infra applique son heuristique.
_STATUS_TOKENS: dict[str, str] = {
    # Disqualification
    "dsq": STATUS_DSQ,
    "disq": STATUS_DSQ,
    "disqualifie": STATUS_DSQ,
    # Pluriel : groupe RaceResult « Disqualifiés ».
    "disqualifies": STATUS_DSQ,
    "disqualified": STATUS_DSQ,
    # `DQ` : forme de fftri.t2area.com (colonne Clt), cf. #51.
    "dq": STATUS_DSQ,
    # Abandon (Did Not Finish)
    "dnf": STATUS_DNF,
    "abd": STATUS_DNF,
    "abandon": STATUS_DNF,
    # Pluriel : RaceResult nomme ses groupes de statut « Abandons ».
    "abandons": STATUS_DNF,
    "ab": STATUS_DNF,
    # Hors délai (barrière horaire) : « OTL » d'Embrunman, RaceResult 350635 (#970).
    "otl": STATUS_DNF,
    "hd": STATUS_DNF,
    "horsdelai": STATUS_DNF,
    "horsdelais": STATUS_DNF,
    # Non-partant (Did Not Start)
    "dns": STATUS_DNS,
    "nonpartant": STATUS_DNS,
    # Pluriel : groupe RaceResult « Non Partants ».
    "nonpartants": STATUS_DNS,
    "np": STATUS_DNS,
    "forfait": STATUS_DNS,
    "ff": STATUS_DNS,
    # Finisher — label positif explicite, utilisé seulement si un provider le pose
    "finisher": STATUS_FINISHER,
    "classe": STATUS_FINISHER,
    "fin": STATUS_FINISHER,
    "ok": STATUS_FINISHER,
}

def _normalize_label(label: str) -> str:
    """Minuscule, sans accents, ne garde que les caractères alphanumériques.

    'Non partant' → 'nonpartant' ; 'Disqualifié' → 'disqualifie'.
    """
    s = strip_accents(label.strip().lower())
    return re.sub(r"[^a-z0-9]", "", s)


def derive_status_from_label(label: str) -> str:
    """Traduit un label de statut brut en constante STATUS_* (ou "" si inconnu).

    "" (vide / non reconnu) est le défaut sûr : services/mapping.derive_status
    retombe alors sur son heuristique (finisher si temps total, sinon DNF),
    comportement identique à aujourd'hui. Comparaison sur le label normalisé →
    insensible à la casse, aux accents et à la ponctuation.
    """
    if not label:
        return ""
    return _STATUS_TOKENS.get(_normalize_label(label), "")


# Genre lu dans une catégorie individuelle (#990), formes relevées sur 17
# épreuves RaceResult : code FFTri/FFA suffixé (`S1M`, `JUM`, `M1-3M`, `M4+F`),
# tranche d'âge préfixée (`M18-34`, `F65+`) et libellé « <classe> H|F »
# (`Seniors F`, `Master 4+ Homme`). Un libellé de sexe nu (`Masculin`, `Hommes`)
# n'est mesuré que sur des relais et des duos : il décrit l'équipe, on l'ignore.
_RE_CODE_SUFFIXE_SEXE = re.compile(r"^(?:[A-Z]{2}|[A-Z]\d{1,2}(?:[-+]\d?)?)([MFH])$")
_RE_TRANCHE_PREFIXE_SEXE = re.compile(r"^([MF])(?:\d{1,2}-\d{1,2}|\d{2}\+)$")
_RE_CATEGORIE_EQUIPE = re.compile(
    r"\b(?:MIXTE|MIXED|RELAIS?|RELAY|DUO|EQUIPE|TEAM)\b|[MFH]\s*\+\s*[MFH]|&"
)
_MOTS_SEXE_MASCULIN = frozenset({"H", "M", "HOMME", "HOMMES", "MASCULIN"})
_MOTS_SEXE_FEMININ = frozenset({"F", "FEMME", "FEMMES", "FEMININ"})


def gender_from_category(category: str) -> str:
    """`"M"`, `"F"` ou `""` déduit d'une catégorie individuelle, jamais d'équipe."""
    code = strip_accents((category or "").strip()).upper()
    if (
        not code
        or code == "FEM"  # « féminin » abrégé, libellé nu malgré sa forme de code
        or _RE_CATEGORIE_EQUIPE.search(code)
        or derive_status_from_label(code)
    ):
        return ""
    mots = re.findall(r"[A-Z0-9+\-]+", code)
    if len(mots) >= 2:
        if mots[-1] in _MOTS_SEXE_MASCULIN:
            return "M"
        if mots[-1] in _MOTS_SEXE_FEMININ:
            return "F"
        return ""
    trouve = _RE_CODE_SUFFIXE_SEXE.match(code) or _RE_TRANCHE_PREFIXE_SEXE.match(code)
    if not trouve:
        return ""
    return "F" if trouve.group(1) == "F" else "M"


def qualify_event_name(event_name: str, qualifiant: str) -> str:
    """Qualifie un nom d'épreuve par son parcours / contest.

    « Triathlon de Rumilly » + « Distance M » → « Triathlon de Rumilly - Distance M ».
    Chaque parcours est une épreuve distincte (classement propre, dossards
    réutilisés d'un parcours à l'autre) : sans qualification, plusieurs parcours
    de même type fusionnent en une seule Course et leurs dossards entrent en
    collision (issue #21 : participants manquants, rangs dupliqués). Un
    qualifiant déjà présent dans le nom n'est pas ré-ajouté.
    """
    # Espaces réduits des deux côtés : un nom d'événement à espace final
    # doublait l'espace devant ` - ` (#1088).
    event_name = collapse_spaces(event_name)
    qualifiant = collapse_spaces(qualifiant)
    if not qualifiant or qualifiant.lower() in event_name.lower():
        return event_name
    return f"{event_name} - {qualifiant}"


def collapse_spaces(value: str | None) -> str:
    """Rogne et réduit à un seul espace toute suite de blancs."""
    return " ".join((value or "").split())

"""
Classifieur unique de disciplines — **seule source de vérité**.

Remplace les `_detect_event_type` jadis dupliqués dans chaque scraper. Les
scrapers délèguent ici ; la migration de re-classement réutilise les mêmes
fonctions. Voir la note `registry.py` sur la factorisation.

Forme canonique d'un `event_type` : minuscules, tirets, sport en base +
suffixe de taille optionnel. Le kilométrage exact n'entre jamais dans le slug
(il vit dans `Course.distance_km`).
"""
import re

# Bases de sport « nues » (sans taille). Sert au re-classement à savoir si une
# valeur peut être raffinée. `trail` est volontairement nu (distance via km).
BARE_TYPES = frozenset({
    "triathlon", "duathlon", "swimrun", "cyclisme", "course-a-pied", "trail",
})

# Tous les slugs canoniques produits par le classifieur. Sert à garantir
# l'idempotence stricte de `normalize_event_type` (un slug déjà propre est
# renvoyé tel quel, sans risque de re-classement erroné).
CANONICAL_TYPES = frozenset({
    "triathlon", "triathlon-xs", "triathlon-s", "triathlon-m", "triathlon-l",
    "triathlon-xl",
    "duathlon", "duathlon-xs", "duathlon-s", "duathlon-m", "duathlon-l",
    "swimrun", "swimrun-s", "swimrun-m", "swimrun-l",
    "aquathlon", "aquarun", "bike-run",
    "course-a-pied", "course-a-pied-5k", "course-a-pied-10k",
    "course-a-pied-semi", "course-a-pied-marathon",
    "trail", "cyclisme", "cyclisme-route", "cyclisme-clm",
})


def _norm(text: str) -> str:
    return (text or "").lower().strip()


def _detect_size(t: str) -> str:
    """Renvoie la taille détectée : "", "xs", "s", "m", "l", "xl".

    Gère à la fois les slugs (`-m-`, fin `-l`, `format-m`) et les noms humains
    (`olympique`, `sprint`, `longue`, `70.3`, `ironman`…). Ordre : du plus
    grand au plus petit, XL avant L, XS testé après S (un slug `-xs-` ne
    déclenche pas la frontière `-s-`).
    """
    def seg(tag: str) -> bool:
        # Token de taille isolé : non entouré d'alphanumériques. Couvre tous les
        # délimiteurs (espace, tiret, début/fin) sans énumérer chaque motif —
        # « triathlon-s », « format-s », « triathlon s », « Relais S-Entreprises »
        # matchent ; le « s » final de « relais » ou celui de « xs » non (précédé
        # d'une lettre). XS reste testé après S grâce à l'ordre de _detect_size.
        return re.search(rf"(?<![a-z0-9]){tag}(?![a-z0-9])", t) is not None

    if "xxl" in t or "ironman" in t or "embrunman" in t or seg("xl"):
        return "xl"
    if "longue" in t or "half" in t or "70.3" in t or seg("l"):
        return "l"
    if "olymp" in t or seg("m"):
        return "m"
    if "sprint" in t or "decouverte" in t or "découverte" in t or seg("s"):
        return "s"
    if "extra" in t or seg("xs"):
        return "xs"
    return ""


def _triathlon(t: str) -> str:
    size = _detect_size(t)
    if not size:
        return "triathlon"
    return f"triathlon-{size}"


def _course_a_pied(t: str) -> str | None:
    """Course à pied (route) avec format nommé, ou None si non reconnu."""
    is_cap = (
        "marathon" in t or "semi" in t
        or re.search(r"\b\d+\s*k(m)?\b", t)
        or "course à pied" in t or "course a pied" in t
        or "course sur route" in t or "course pédestre" in t
        or "course pedestre" in t or "foulées" in t or "foulees" in t
        or "corrida" in t or "running" in t
    )
    if not is_cap:
        return None
    if "semi" in t or "half" in t:
        return "course-a-pied-semi"
    if "marathon" in t:
        return "course-a-pied-marathon"
    if re.search(r"\b10\s*k(m)?\b", t):
        return "course-a-pied-10k"
    if re.search(r"\b5\s*k(m)?\b", t):
        return "course-a-pied-5k"
    return "course-a-pied"


def _cyclisme(t: str) -> str | None:
    """Cyclisme route / CLM, ou None si non reconnu."""
    is_velo = (
        "cyclisme" in t or "cyclo" in t or "cyclosport" in t
        or "gran fondo" in t or "granfondo" in t
        or "vélo" in t or "velo" in t
    )
    if not is_velo:
        return None
    if "contre-la-montre" in t or "contre la montre" in t or re.search(r"\bclm\b", t):
        return "cyclisme-clm"
    if "route" in t or "cyclosport" in t:
        return "cyclisme-route"
    return "cyclisme"


def classify_event_type(text: str) -> str:
    """Texte libre (nom d'épreuve, heat+slug, parcours…) → slug canonique."""
    t = _norm(text)

    # 1. Multisports composites d'abord (sous-mots piégeux).
    if "swimrun" in t or "swim-run" in t or "swim run" in t or "swim&run" in t:
        size = _detect_size(t)
        return f"swimrun-{size}" if size in ("s", "m", "l") else "swimrun"
    if (
        (re.search(r"\bbike\b", t) and re.search(r"\brun\b", t))
        or "bikerun" in t or "bike-run" in t
    ):
        return "bike-run"
    if "aquathlon" in t:
        return "aquathlon"
    if "aquarun" in t:
        return "aquarun"
    if "duathlon" in t:
        size = _detect_size(t)
        return f"duathlon-{size}" if size else "duathlon"

    # 2. Triathlon explicite : logique de distance (avant les mono-sports, car
    #    "half" est ambigu — half-marathon vs half-ironman).
    if "triathlon" in t:
        return _triathlon(t)

    # 3. Mono-sports nouveaux.
    if "trail" in t:
        return "trail"
    cyc = _cyclisme(t)
    if cyc:
        return cyc
    cap = _course_a_pied(t)
    if cap:
        return cap

    # 4. Repli : triathlon nu (+ taille si déductible : « Sprint … », « Ironman … »).
    return _triathlon(t)


def normalize_event_type(value: str) -> str:
    """Canonicalise une valeur existante (`Triathlon M` → `triathlon-m`).

    Idempotent : un slug déjà canonique est renvoyé tel quel (court-circuit),
    ce qui couvre aussi les slugs nus comme `course-a-pied`.
    """
    v = _norm(value)
    if v in CANONICAL_TYPES:
        return v
    return classify_event_type(value)


def extract_distance_km(text: str) -> float | None:
    """Extrait un kilométrage explicite (`23 km`, `42,2 km`, `120km`)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*km\b", _norm(text))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))

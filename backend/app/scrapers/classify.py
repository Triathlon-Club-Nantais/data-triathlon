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
    "duathlon-xl",
    "swimrun", "swimrun-s", "swimrun-m", "swimrun-l",
    "aquathlon", "aquathlon-xs", "aquathlon-s", "aquathlon-m", "aquathlon-l",
    "aquathlon-xl",
    "aquarun", "bike-run",
    # Nouvelles disciplines de la saisie manuelle (#270).
    "swim-bike", "swim-bike-xs", "swim-bike-s", "swim-bike-m", "swim-bike-l",
    "swim-bike-xl",
    "cross-triathlon", "raid-multisport",
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

    # Un format half explicite prime sur le jeton de marque « ironman », qui
    # vaut sinon XL : « IRONMAN 70.3 Vichy » est un half, pas un format long
    # (issue #54). « Ironman France », sans marqueur, reste XL.
    if "70.3" in t or "half" in t:
        return "l"
    if "xxl" in t or "ironman" in t or "embrunman" in t or seg("xl"):
        return "xl"
    if "longue" in t or seg("l"):
        return "l"
    if "olymp" in t or seg("m"):
        return "m"
    if "sprint" in t or "decouverte" in t or "découverte" in t or seg("s"):
        return "s"
    if "extra" in t or seg("xs"):
        return "xs"
    return ""


# Tailles admises par sport : hors de cette table, un sport n'est jamais suffixé
# (« Trail du Mont Blanc L » reste `trail`, la distance vivant dans `distance_km`).
_TAILLES_PAR_SPORT = {
    "triathlon": ("xs", "s", "m", "l", "xl"),
    "duathlon": ("xs", "s", "m", "l", "xl"),
    "swimrun": ("s", "m", "l"),
    "swim-bike": ("xs", "s", "m", "l", "xl"),
}


def _avec_taille(base: str, t: str) -> str:
    """Sport nu + taille détectée dans `t`, si ce sport en admet une."""
    tailles = _TAILLES_PAR_SPORT.get(base)
    if not tailles:
        return base
    size = _detect_size(t)
    return f"{base}-{size}" if size in tailles else base


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


def _sport_base(t: str) -> str | None:
    """Sport **nommé** dans `t`, sans suffixe de taille. None si aucun ne l'est.

    Le None est porteur : il distingue « ce texte nomme un sport » de « il faut se
    replier », ce qui permet à `classify_event_type` de ne consulter son contexte
    qu'à défaut.
    """
    # 1. Multisports composites d'abord (sous-mots piégeux).
    if "swimrun" in t or "swim-run" in t or "swim run" in t or "swim&run" in t:
        return "swimrun"
    if re.search(r"swim\s*[-&]?\s*bike", t):
        return "swim-bike"
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
        return "duathlon"

    # 2. Triathlon explicite, avant les mono-sports : « half » est ambigu
    #    (half-marathon vs half-ironman).
    if "triathlon" in t:
        return "triathlon"

    # 3. Mono-sports.
    if "trail" in t:
        return "trail"
    return _cyclisme(t) or _course_a_pied(t)


def classify_event_type(text: str, *, contexte: str = "") -> str:
    """Texte libre (nom d'épreuve, heat+slug, parcours…) → slug canonique.

    `contexte` — texte d'appoint, typiquement le titre de l'événement qui porte
    l'épreuve. Il est consulté **seulement** si `text` ne nomme aucun sport, et ne
    peut donc pas dégrader une épreuve annexe : le « Trail 12 km » d'un
    « Triathlon de X » reste un trail — sur la concaténation des deux, il sortait
    en triathlon, s'affichait comme tel et survivait au filtre `federal_only`.
    La taille, elle, reste celle de `text` dès qu'il en porte une (le « Format S »
    d'un « Triathlon L de Mimizan » est un S), le contexte ne la fournissant qu'à
    défaut.
    """
    t = _norm(text)
    base = _sport_base(t)
    reference = t
    if base is None and contexte:
        reference = f"{_norm(contexte)} {t}".strip()
        base = _sport_base(reference)
    # Repli : triathlon nu (+ taille si déductible : « Sprint … », « Ironman … »).
    return _avec_taille(base or "triathlon", t if _detect_size(t) else reference)


def normalize_event_type(value: str) -> str:
    """Canonicalise une valeur existante (`Triathlon M` → `triathlon-m`).

    Idempotent : un slug déjà canonique est renvoyé tel quel (court-circuit),
    ce qui couvre aussi les slugs nus comme `course-a-pied`.
    """
    v = _norm(value)
    if v in CANONICAL_TYPES:
        return v
    return classify_event_type(value)


def refine_from_splits(event_type: str, *, has_swim: bool, has_bike: bool) -> str:
    """Corrige `event_type` d'après les splits effectivement scrapés (#679).

    « Foulées » nomme la catégorie « open » d'un triathlon chez certains
    organisateurs (Diaoulman Pontivy) : `classify_event_type` seule, qui ne lit
    que le nom, classe alors un heat triathlon complet en `course-a-pied`.
    Une vraie course à pied ne publie jamais de natation **et** de vélo — quand
    la page détail d'un participant fournit les deux, ce sont des segments
    impossibles pour ce sport, qui priment sur le libellé et corrigent le slug
    nu `course-a-pied` en `triathlon` (repli bare déjà utilisé par
    `classify_event_type` — voir `_avec_taille`). Volontairement strict :
    seul le slug nu est concerné, jamais ses suffixes de distance
    (`course-a-pied-5k`…), dont le nom est un signal sans ambiguïté contrairement
    à « foulées ». Ne généralise pas non plus à tout `BARE_TYPES` : le mode de
    défaillance visé (nom qui pointe vers course-a-pied alors que les splits
    disent triathlon) n'a, à ce jour, été observé que sur ce sport.
    """
    if event_type == "course-a-pied" and has_swim and has_bike:
        return "triathlon"
    return event_type


def extract_distance_km(text: str) -> float | None:
    """Extrait un kilométrage explicite (`23 km`, `42,2 km`, `120km`)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*km\b", _norm(text))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))

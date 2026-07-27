"""
Scraper ok-time.fr — API JSON WordPress publique (issue #52).

`classement.ok-time.fr` est une SPA React, mais toutes ses données transitent par
une route WordPress publique. **Un seul appel** rend l'événement entier, toutes
épreuves comprises :

    GET https://ok-time.fr/wp-json/gmcap/v1/evenements/{eventId}/results

Ni Playwright ni parsing HTML sur le chemin nominal : le seul GET HTML sert à
lire l'id d'événement quand l'URL est de la forme éditoriale `/evenement/<slug>/`.

Flux (cf. docs/superpowers/specs/2026-07-26-oktime-scraper-design.md) :
  1. `_parse_url`         → id direct, ou slug à résoudre
  2. `_resolve_event_id`  → 1 GET HTML, id lu dans le lien de classement
  3. `_fetch_results`     → l'appel API, erreurs de la source traduites
  4. `_course_results`    → une épreuve de la charge → participants
  5. toutes les épreuves de l'événement sont importées (comme les heats
     Breizh Chrono et les onglets chronoplace)

L'API n'expose aucune route par épreuve : une URL pointant une épreuve rapporte
toujours l'événement entier.
"""
import html
import logging
import re
from datetime import date, datetime
from urllib.parse import urlparse

import httpx

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER, ScrapedResult
from .classify import classify_event_type
from .utils import normalize_rank, normalize_time, qualify_event_name, split_athlete_name

logger = logging.getLogger(__name__)

BASE_URL = "https://ok-time.fr"
API_PATH = "/wp-json/gmcap/v1/evenements/{event_id}/results"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# `classement.ok-time.fr/<id>` ou `.../<id>/race/<raceId>`. Le segment `race`
# est **ignoré** : l'API ne sait pas filtrer par épreuve, elle rend l'événement.
_ID_PATH_RE = re.compile(r"^/(?P<id>\d+)(?:/race/\d+)?/?$")
# Forme éditoriale actuelle du site.
_SLUG_PATH_RE = re.compile(r"^/evenement/(?P<slug>[^/]+)/?$")
# Formes retirées du site : les 3 URLs mortes du Sheet (§2.1 du design).
_PREFIXES_OBSOLETES = ("/course/", "/competition/")


def _parse_url(url: str) -> tuple[str, str]:
    """(id d'événement, slug) — exactement l'un des deux est non vide.

    Un slug devra être résolu par une requête HTML ; un id part directement à
    l'API. L'id de l'URL de classement **est** le post-id WordPress attendu par
    l'API (vérifié sur les 21 événements du panel) : aucune table de
    correspondance à maintenir.
    """
    path = urlparse(url).path or "/"
    m = _ID_PATH_RE.match(path)
    if m:
        return m.group("id"), ""
    m = _SLUG_PATH_RE.match(path)
    if m:
        return "", m.group("slug")
    if any(path.startswith(prefixe) for prefixe in _PREFIXES_OBSOLETES):
        raise ValueError(
            f"URL ok-time.fr obsolète : {url} — les préfixes /course/ et "
            "/competition/ ont été retirés du site, qui publie sous "
            "/evenement/<slug>/. Lien à corriger à la source."
        )
    raise ValueError(f"URL ok-time.fr non reconnue : {url}")


# Le lien de classement d'une page `/evenement/<slug>/`. Cherché à la regex sur
# le HTML brut plutôt qu'au parseur : le lien peut vivre dans un attribut, un
# bloc de script ou une iframe selon le thème, et un seul motif les couvre tous.
_CLASSEMENT_ID_RE = re.compile(r"classement\.ok-time\.fr/(\d+)")


def _resolve_event_id(client: httpx.Client, slug: str) -> str:
    """Id d'événement lu sur la page éditoriale. 1 GET HTML, aucun autre usage.

    Une page servie mais dépourvue de lien de classement est le cas des slugs
    redirigés vers le listing générique (§2.1 du design) : il n'y a rien à en
    tirer, l'erreur doit le dire.
    """
    url = f"{BASE_URL}/evenement/{slug}/"
    response = client.get(url)
    response.raise_for_status()
    m = _CLASSEMENT_ID_RE.search(response.text)
    if not m:
        raise ValueError(
            f"Page ok-time.fr « {slug} » sans aucun lien de classement : "
            "événement sans résultats publiés, ou slug redirigé vers le listing."
        )
    return m.group(1)


def _fetch_results(client: httpx.Client, event_id: str) -> dict:
    """La charge JSON de l'événement entier. Erreurs de la source traduites.

    L'API distingue ses deux échecs métier (§1.3 du design), on les garde
    distincts : un 404 dit « cet id n'existe pas », un 400 dit « cet événement
    existe mais n'a rien publié ». Toute autre erreur HTTP (5xx…) remonte telle
    quelle : ce n'est pas un problème de lien, et la traduire en ValueError la
    ferait passer pour tel dans le bilan CLI.
    """
    url = f"{BASE_URL}{API_PATH.format(event_id=event_id)}"
    response = client.get(url)
    if response.status_code == 404:
        raise ValueError(
            f"Événement ok-time introuvable (id {event_id}) : seul un id "
            "d'événement est accepté, pas un id d'épreuve."
        )
    if response.status_code == 400:
        raise ValueError(
            f"Événement ok-time {event_id} : aucun résultat publié à ce jour."
        )
    response.raise_for_status()
    charge = response.json()
    if not isinstance(charge, dict) or "data" not in charge:
        raise ValueError(
            f"Charge ok-time inattendue pour l'événement {event_id} : "
            "clé « data » absente."
        )
    return charge


# --------------------------------------------------------------------------- #
# Identité de l'athlète
# --------------------------------------------------------------------------- #

def _repair_mojibake(s: str) -> str:
    """Répare un texte UTF-8 relu en cp1252 (« AnaÃ¯s » → « Anaïs »).

    Mesuré sur `nom` **uniquement** (173 participations du panel, concentrées sur
    les 4 événements les plus anciens) : `club` et `categorie` en sont indemnes,
    on ne les touche donc pas.

    La conversion n'est retenue que si elle **aboutit** : un nom déjà sain
    échoue au décodage UTF-8 (« Anaïs » → b'Ana\\xefs', 0xEF sans continuation
    valide) et ressort inchangé. Un caractère hors cp1252 (« Łukasz ») échoue à
    l'encodage, même issue. Contrôle de non-régression : les 1 061 noms
    accentués sains du panel traversent intacts.
    """
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")
# Marqueurs d'une course d'équipes dans le titre, comparés sans accents ni casse.
_RELAY_TITRE_RE = re.compile(r"relais|equipe|duo|team")
# Séparateur de coéquipiers dans un nom (« GUILLON RÉMI / CHARPENTIER EMMANUEL »).
# Testé sans les espaces qui l'entourent : une graphie collée resterait un binôme.
_SEPARATEUR_EQUIPE = "/"


def _is_relay_course(title: str, runners: list[dict]) -> bool:
    """`is_relay` de **toute** la course : titre parlant, ou majorité de binômes.

    Décidé au niveau de la course, jamais du participant : sinon
    `Course.is_relay` et `Participation.is_relay` divergeraient selon l'ordre des
    participants dans la charge.

    Le titre seul ne suffit pas (les courses du Bike & Run de la pomme et de la
    châtaigne sont des binômes muets), et « au moins un » ne convient pas non
    plus (il basculerait « Format M individuel », 1 nom sur 57, en relais). D'où
    la **majorité stricte**.
    """
    if _RELAY_TITRE_RE.search((title or "").lower().translate(_ACCENTS)):
        return True
    noms = [str(runner.get("nom") or "") for runner in runners]
    if not noms:
        return False
    binomes = sum(1 for nom in noms if _SEPARATEUR_EQUIPE in nom)
    return binomes * 2 > len(noms)


def _athlete_identity(runner: dict, *, is_relay: bool, epreuve_id: str) -> tuple[str, str]:
    """(nom, prénom) — un nom d'équipe n'est jamais découpé (précédent #63).

    Trois régimes :

    1. `rgpd:"N"` — la source ampute le nom (« T... B... ») mais publie temps et
       rang. Identité synthétique « Anonyme <epreuve_id>-<dossard> », prénom
       vide. La clé d'épreuve est **indispensable** : `Athlete` étant unique sur
       (nom, prénom, date de naissance), un simple « Anonyme 927 » fusionnerait
       les dossards 927 anonymes de deux courses en un athlète agrégeant les
       résultats de deux personnes. `epreuve_id` et `dossard` étant stables,
       l'identité l'est d'un re-scrape à l'autre. Si ok-time levait l'anonymat,
       la réconciliation d'identité (#66) rattacherait les participations au nom
       réel au prochain `rescrape-db`.
    2. équipe (course de relais, ou nom porteur d'un « / ») — le nom entier va
       dans `nom`, le prénom reste vide. Ne pas mutiler un nom d'équipe.
    3. sinon — convention « Prénom NOM » de la source, déléguée à
       `split_athlete_name`.
    """
    if str(runner.get("rgpd") or "").strip().upper() == "N":
        return f"Anonyme {epreuve_id}-{runner.get('dossard')}", ""
    nom = _repair_mojibake(str(runner.get("nom") or "").strip())
    if is_relay or _SEPARATEUR_EQUIPE in nom:
        return nom, ""
    return split_athlete_name(nom)


# --------------------------------------------------------------------------- #
# Scalaires du participant
# --------------------------------------------------------------------------- #

def _drapeau(runner: dict, champ: str) -> str:
    """Un drapeau O/N de la source, normalisé en majuscule."""
    return str(runner.get(champ) or "").strip().upper()


def _status(runner: dict, *, course_non_chronometree: bool) -> str:
    """Statut sportif, ou "" pour laisser l'heuristique du projet trancher.

    Ordre de priorité : **DNS avant DNF** — 1 participation du panel porte
    `abandon="O"` et `pris_depart="N"`, et ne pas être parti prime.

    Le repli `finisher` est borné à une course **entièrement** non chronométrée
    (les 3 courses enfants du panel, `status="finish"` sans aucun temps) : dans
    une course par ailleurs chronométrée, un participant sans temps reste traité
    par l'heuristique, faute de savoir le distinguer d'un abandon non saisi.
    """
    if _drapeau(runner, "pris_depart") == "N":
        return STATUS_DNS
    if _drapeau(runner, "abandon") == "O":
        return STATUS_DNF
    if _drapeau(runner, "disqualifie") == "O":
        return STATUS_DSQ
    if course_non_chronometree:
        return STATUS_FINISHER
    return ""


def _rank(value) -> int | None:
    """Rang, avec `0 → None` : la source dit « non classé » avec un zéro.

    1 336 finishers valides du panel sur 11 816 sont dans ce cas.
    `normalize_rank` rendrait 0, qui s'afficherait comme une place.
    """
    return normalize_rank(value) or None


def _gender(raw) -> str:
    """« M » / « F » tels quels ; tout le reste → "".

    `X` (relais mixtes, 323 participations) n'est pas rendu par le front : mieux
    vaut vide qu'une valeur qu'il ne sait pas afficher.
    """
    genre = str(raw or "").strip().upper()
    return genre if genre in ("M", "F") else ""


def _total_time(runner: dict) -> str:
    """`temps_finish` normalisé, vide si `"00:00:00"` — la façon dont la source
    dit « pas de temps » (`temps_finish` est toujours renseigné, 12 644/12 644)."""
    brut = normalize_time(str(runner.get("temps_finish") or "").strip())
    return "" if brut == "00:00:00" else brut


# --------------------------------------------------------------------------- #
# Splits
# --------------------------------------------------------------------------- #
# `_secs` / `_fmt_secs` sont des copies locales de celles de `timepulse` : leur
# factorisation dans `utils.py` est un refacto à part (cf. la note d'en-tête de
# `registry.py`), qu'on n'entame pas au fil d'un nouveau provider.

def _secs(t: str) -> int:
    if not t:
        return 0
    p = t.split(":")
    try:
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except (IndexError, ValueError):
        return 0


def _fmt_secs(s: int) -> str:
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _segments(points: list[dict] | None) -> tuple[list[tuple[str, str]], bool]:
    """Points de passage cumulés → durées de segment. (segments, cumuls_conservés).

    Les points sont cumulés depuis le départ (4 512 des 4 522 participations à
    ≥ 2 points le vérifient) ; le projet range des **durées**, convention déjà
    appliquée par `klikego` et `timepulse`.

    Les libellés sont ceux de la source, et les durées vont dans
    `ScrapedResult.segments` — le chemin générique déplafonné — plutôt que dans
    les 5 slots positionnels : les `id` de points ne sont pas sémantiques
    (« 12|2 » vaut « T2 » sur une épreuve et « VELO » sur une autre) et 55 des 99
    courses du panel sortent du motif triathlon. Un remapping devinerait.

    **Garde sur les deltas négatifs** : si un delta sort négatif (les 10
    participations de Mimizan à l'ordre incohérent), la participation conserve
    ses valeurs **cumulées brutes** plutôt qu'un temps absurde, et le second
    membre du tuple le signale à l'appelant, qui journalise par épreuve.

    Le temps total ne vient **jamais** du dernier point : 392 participations ont
    un dernier point différent de `temps_finish` (épreuves finissant sur
    « Départ CAP2 »). `temps_finish` fait seul foi.
    """
    cumules = [
        (str(point.get("nom") or "").strip(), normalize_time(str(point.get("time") or "").strip()))
        for point in points or []
    ]
    # Un point à zéro ne porte aucune durée : le garder ferait sortir un delta
    # négatif au point suivant et déclencherait le repli à tort.
    cumules = [(label, temps) for label, temps in cumules if _secs(temps) > 0]
    if not cumules:
        return [], False

    durees: list[tuple[str, str]] = []
    precedent = 0
    for label, temps in cumules:
        courant = _secs(temps)
        if courant < precedent:
            return cumules, True
        durees.append((label, _fmt_secs(courant - precedent)))
        precedent = courant
    return durees, False


# --------------------------------------------------------------------------- #
# Assemblage
# --------------------------------------------------------------------------- #

def _build_result(
    runner: dict,
    *,
    url: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    distance_km: float | None,
    is_relay: bool,
    epreuve_id: str,
    course_non_chronometree: bool,
    contexte: dict,
) -> ScrapedResult:
    """Un participant de la charge API → un `ScrapedResult`.

    `raw_data` conserve la charge brute du participant — donc les points de
    passage **cumulés d'origine** — plus le contexte d'épreuve non porté par les
    champs typés, de sorte qu'une erreur de différenciation reste diagnosticable
    sans re-scraper.
    """
    nom, prenom = _athlete_identity(runner, is_relay=is_relay, epreuve_id=epreuve_id)
    segments, cumuls_conserves = _segments(runner.get("points_de_passage"))

    result = ScrapedResult(source_url=url, provider="oktime")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date
    result.distance_km = distance_km
    result.is_relay = is_relay
    result.athlete_name = nom
    result.athlete_firstname = prenom
    result.club = str(runner.get("club") or "").strip()
    result.category = str(runner.get("categorie") or "").strip()
    result.gender = _gender(runner.get("sexe"))
    dossard = runner.get("dossard")
    result.bib_number = "" if dossard is None else str(dossard).strip()
    result.rank_overall = _rank(runner.get("classement_general"))
    result.rank_category = _rank(runner.get("classement_categorie"))
    result.rank_gender = _rank(runner.get("classement_sexe"))
    result.total_time = _total_time(runner)
    result.segments = segments
    result.status = _status(runner, course_non_chronometree=course_non_chronometree)
    result.raw_data = {
        **runner,
        **contexte,
        "splits_cumules_conserves": cumuls_conserves,
    }
    return result


# --------------------------------------------------------------------------- #
# Niveau course
# --------------------------------------------------------------------------- #

def _parse_date(raw) -> date | None:
    """`dd/mm/yyyy` — la forme de `date_course` sur les 99 courses du panel."""
    try:
        return datetime.strptime(str(raw or "").strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_distance(raw) -> float | None:
    """`distance_course` en km, virgule décimale (« 27,5 » → 27.5).

    Renseignée sur tout le panel : la fournir évite le repli de
    `mapping.get_or_create_course` sur l'extraction depuis le nom, qui lit
    « Course chronométrée 9,5 km » comme un 5 km. Une distance nulle vaut absence.
    """
    valeur = str(raw or "").strip().replace(",", ".")
    if not valeur:
        return None
    try:
        km = float(valeur)
    except ValueError:
        return None
    return km or None


def _log_cumuls_conserves(resultats: list[ScrapedResult], title_course: str) -> None:
    """Signal **agrégé** (une ligne par épreuve, pas une par participation) du
    repli sur cumulés bruts. Pas d'état global : tout vit dans cet appel."""
    n = sum(1 for r in resultats if r.raw_data.get("splits_cumules_conserves"))
    if n:
        logger.warning(
            "Épreuve ok-time « %s » : %d participation(s) aux points de passage "
            "décroissants — splits conservés en cumulés bruts plutôt qu'en durées.",
            title_course, n,
        )


def _course_results(course: dict, *, url: str, evenement_title: str) -> list[ScrapedResult]:
    """Une épreuve de la charge → ses participants. Pure : aucune requête.

    `evenement_title` est reçu **déjà** décodé (`html.unescape`) par l'appelant :
    la charge porte des entités brutes (`&#8211;`, `&#038;`) dans tous les titres
    concernés, qui partiraient en base telles quelles.

    Une course est **écartée** si `status != "finish"` **et** qu'aucun de ses
    participants n'a de temps : ce sont les listes d'engagés (11 courses / 1 035
    participations au panel), dont l'import créerait autant de participations
    sans temps que l'heuristique du projet classerait DNF. La double condition
    est délibérée — le comportement de `status` sur une course **en cours** n'a
    pas été observé, et écarter sur ce seul critère risquerait de jeter des
    résultats partiels.
    """
    title_course = html.unescape(str(course.get("title_course") or "").strip())
    runners = course.get("runners") or []
    statut_course = str(course.get("status") or "").strip()
    non_chronometree = not any(_total_time(runner) for runner in runners)

    if statut_course != "finish" and non_chronometree:
        logger.info(
            "Épreuve ok-time « %s » écartée : liste d'engagés (status=%r, "
            "%d participant(s), aucun temps).",
            title_course, statut_course, len(runners),
        )
        return []

    epreuve_id = str(course.get("epreuve_id") or "")
    # Type classé sur la **concaténation** des deux titres : le titre d'épreuve
    # seul est trompeur (« Format M individuel » du SwimRun Côte Beauté sortirait
    # en triathlon-m, « La Bourriquette » du Trail du Bourraid en triathlon). Sur
    # les 99 courses du panel, la concaténation en corrige 5 et n'en dégrade aucune.
    resultats = [
        _build_result(
            runner,
            url=url,
            event_name=qualify_event_name(evenement_title, title_course),
            event_type=classify_event_type(f"{evenement_title} {title_course}"),
            event_date=_parse_date(course.get("date_course")),
            distance_km=_parse_distance(course.get("distance_course")),
            is_relay=_is_relay_course(title_course, runners),
            epreuve_id=epreuve_id,
            course_non_chronometree=non_chronometree,
            contexte={
                "epreuve_id": epreuve_id,
                "heuredebut_course": course.get("heuredebut_course"),
                "reference_epreuve": course.get("reference_epreuve"),
                "status_course": statut_course,
            },
        )
        for runner in runners
    ]
    _log_cumuls_conserves(resultats, title_course)
    return resultats


# --------------------------------------------------------------------------- #
# Point d'entrée
# --------------------------------------------------------------------------- #

def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants de **toutes** les épreuves de l'événement.

    L'API n'expose aucune route par épreuve : une URL pointant une épreuve
    rapporte l'événement entier, et on l'importe entier — comme les heats Breizh
    Chrono et les onglets chronoplace. Coût : un appel, deux si l'URL est de la
    forme éditoriale `/evenement/<slug>/`.

    `source_url` reste l'URL **demandée** : c'est la clé de cache TTL, elle doit
    correspondre au lien du Sheet et non à une forme reconstruite.
    """
    event_id, slug = _parse_url(url)
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if not event_id:
            event_id = _resolve_event_id(client, slug)
        charge = _fetch_results(client, event_id)

    evenement_title = html.unescape(str(charge.get("evenement_title") or "").strip())
    resultats: list[ScrapedResult] = []
    for course in charge.get("data") or []:
        resultats.extend(
            _course_results(course, url=url, evenement_title=evenement_title)
        )
    return resultats

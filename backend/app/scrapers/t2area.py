"""
Scraper fftri.t2area.com — plateforme de résultats officielle de la FFTRI.

Un Joomla qui rend le classement complet en HTML server-rendered : une requête
ramène toutes les lignes (901 sur La Baule M 2022), il n'y a **aucune
pagination**, donc ni API à rétro-concevoir ni Playwright.

La profondeur du chemin dit à quel niveau on est :

    /calendrier/<événement>.html                          événement (refusé)
    /calendrier/<événement>/<épreuve>.html                épreuve (année à résoudre)
    /calendrier/<événement>/<épreuve>/<année>.html        édition ← le classement
    /calendrier/<événement>/<épreuve>/<année>/<clé>.html  fiche individuelle

Flux (cf. docs/scrapers/t2area.md, re-sondé le 30/09/2026 pour #898) :
  1. `_parse_url`      → (événement, épreuve, année) ; une fiche est tronquée
                         vers son édition (le cas réel du Sheet)
  2. `_resolve_annee`  → année absente : 1 GET sur l'épreuve, on prend la plus récente
  3. `_fetch_edition`  → GET du classement, en repérant la redirection vers l'accueil
  4. `_parse_edition`  → un `article.edition-result` par participant, splits compris
  5. `_parse_fiche`    → pour les **seules** lignes `is_tcn` : GET de la fiche,
                         rangs « Sexe » et « Catégorie » (25 requêtes sur La Baule, pas 901)
"""
import logging
import re
from datetime import date
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core import http
from app.core.club import is_tcn

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .classify import classify_event_type
from .utils import (
    DEFAULT_HEADERS,
    derive_status_from_label,
    heat_is_relay,
    normalize_rank,
    normalize_time,
    split_athlete_name,
    strip_accents,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://fftri.t2area.com"
HOST = "fftri.t2area.com"
HEADERS = {**DEFAULT_HEADERS}

_PREFIXE = "/calendrier/"
_ANNEE_RE = re.compile(r"^\d{4}$")

def _norm(text: str) -> str:
    """Minuscule, sans accents, espaces aplatis. « Détails » → « details »."""
    sans_accents = strip_accents((text or "").strip().lower())
    return re.sub(r"\s+", " ", sans_accents)


def _parse_url(url: str) -> tuple[str, str, str]:
    """(événement, épreuve, année). L'année est "" si l'URL n'en porte pas.

    Une **fiche individuelle est tronquée** vers son édition : c'est la forme que
    porte le Sheet. Une **URL d'événement est refusée** : ses épreuves ont des
    dernières éditions d'années différentes (La Baule : `triathlon-m` en 2022,
    `triathlon-jeunes-1` en 2024), un fan-out dont l'année varierait d'une
    épreuve à l'autre n'aurait pas de sens. Un appel = une `Course`.
    """
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() != HOST:
        raise ValueError(f"URL hors fftri.t2area.com : {url}")
    chemin = parsed.path
    if not chemin.startswith(_PREFIXE) or not chemin.endswith(".html"):
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    parts = chemin[len(_PREFIXE):-len(".html")].split("/")
    if not all(parts):
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    if len(parts) == 1:
        raise ValueError(
            f"URL d'événement fftri.t2area.com ({parts[0]}) : pointez une épreuve "
            "ou une édition, un événement en porte plusieurs."
        )
    if len(parts) > 4:
        raise ValueError(f"URL fftri.t2area.com non reconnue : {url}")
    evenement, epreuve = parts[0], parts[1]
    if len(parts) == 2:
        return evenement, epreuve, ""
    annee = parts[2]
    if not _ANNEE_RE.match(annee):
        raise ValueError(f"Année illisible dans l'URL fftri.t2area.com : {url}")
    return evenement, epreuve, annee


def _epreuve_url(evenement: str, epreuve: str) -> str:
    return f"{BASE_URL}{_PREFIXE}{evenement}/{epreuve}.html"


def _edition_url(evenement: str, epreuve: str, annee: str) -> str:
    return f"{BASE_URL}{_PREFIXE}{evenement}/{epreuve}/{annee}.html"


def _fetch(client: httpx.Client, url: str) -> str:
    response = client.get(url)
    response.raise_for_status()
    return response.text


class EditionIntrouvableError(ValueError):
    """L'édition n'existe pas : le site répond **303 vers son calendrier**."""


def _fetch_edition(client: httpx.Client, url: str) -> str:
    """GET du classement. Une édition inexistante répond 303 vers
    `/calendrier.html`, donc 200 après la redirection : c'est l'URL finale qui la
    démasque, distincte d'un markup inconnu (#898)."""
    response = client.get(url)
    response.raise_for_status()
    finale = str(getattr(response, "url", "") or url)
    if urlparse(finale).path != urlparse(url).path:
        raise EditionIntrouvableError(
            f"Édition inexistante sur fftri.t2area.com : {url} redirige vers {finale}."
        )
    return response.text


def _resolve_annee(client: httpx.Client, evenement: str, epreuve: str) -> str:
    """Année de la dernière édition publiée, lue sur la page d'épreuve.

    Regex sur les `href` bruts plutôt que sur une classe CSS : les liens portent
    `class="btn-fx-1"`, un décor qui peut changer, alors que la forme de l'URL
    est structurelle.
    """
    url = _epreuve_url(evenement, epreuve)
    html = _fetch(client, url)
    motif = re.compile(
        rf"{re.escape(_PREFIXE)}{re.escape(evenement)}/{re.escape(epreuve)}/(\d{{4}})\.html"
    )
    annees = set(motif.findall(html))
    if not annees:
        raise ValueError(f"Aucune édition publiée pour l'épreuve fftri.t2area.com : {url}")
    return max(annees)


_BIB_RE = re.compile(r"^bib-(\d+)$", re.I)

# Abréviation d'équipe propre aux slugs FFTRI (`swim-run-m-eq`), en jeton isolé :
# le « eq » de « equipe » ne doit pas être capté par accident. Les autres mots
# d'équipe viennent du détecteur commun (#963).
_EQUIPE_RE = re.compile(r"(?<![a-z0-9])eq(?![a-z0-9])")

# Le `<title>` porte l'en-tête (le `<h1>` ne dit plus que « Édition 2022 ») :
#   « Résultats du Triathlon de La Baule - M - 2022 - édition du 18-09-2022 »
# Deux regex **indépendantes** : un libellé inattendu ne doit pas faire perdre la
# date, qui entre dans l'identité de la Course (UNIQUE(name, event_date, event_type)).
_RE_NOM = re.compile(r"r[ée]sultats\s+d[eu]s?\s+(.+?)\s+-\s+\d{4}\s+-\s+[ée]dition\b", re.I)
_RE_DATE = re.compile(r"[ée]dition\s+du\s+(\d{2})-(\d{2})-(\d{4})", re.I)

#: Lien de la fiche individuelle, le seul `edition-details-link` qui reste sous
#: `/calendrier/` (les autres mènent à l'athlète et au club).
_LIEN_FICHE = "a.edition-details-link[href*='/calendrier/']"


def _texte(carte, selecteur: str) -> str:
    element = carte.select_one(selecteur)
    return element.get_text(" ", strip=True) if element else ""


def _ligne(carte) -> dict:
    """Une carte `article.edition-result` → ses champs bruts.

    Le club se lit sans son badge de catégorie ni le « · » qui les sépare ; un
    badge sans lettre ni chiffre (« --- », ligne anonyme) vaut catégorie absente.
    """
    club_element = carte.select_one(".edition-club")
    badge = _texte(carte, ".edition-cat-badge")
    club = ""
    if club_element is not None:
        for enfant in club_element.select(".edition-cat-badge"):
            enfant.extract()
        club = club_element.get_text(" ", strip=True).rstrip("·").strip()
    lien = carte.select_one(_LIEN_FICHE)
    return {
        "clt": _texte(carte, ".edition-rank"),
        "nom": _texte(carte, ".edition-name"),
        "club": club,
        "cat": badge if any(c.isalnum() for c in badge) else "",
        "genre": (carte.get("data-gender") or "").strip().upper(),
        "league": (carte.get("data-league") or "").strip(),
        "temps": _texte(carte, ".edition-time"),
        "details_href": lien["href"].strip() if lien else "",
        "splits": [
            (_texte(split, "small"), _texte(split, "b"))
            for split in carte.select(".edition-split")
        ],
    }


def _cle_fiche(href: str) -> str:
    """Dernier segment du href de la colonne Détails, sans son « .html »."""
    dernier = urlparse(href).path.rsplit("/", 1)[-1]
    return dernier[:-len(".html")] if dernier.endswith(".html") else dernier


def _dossard(cle: str) -> str:
    """Dossard **seulement** si la clé de fiche en est un (`bib-566` → « 566 »).

    La source n'affiche jamais de dossard ; la clé de fiche est tantôt un dossard,
    tantôt une licence FFTRI (`A44719`), tantôt un identifiant interne
    (`id-1153352`). Remplir `bib_number` avec les deux autres ferait mentir le
    champ — le front afficherait « #A44719 ». Les éditions sans dossard retombent
    sur l'appariement par athlète (`import_persistence`).
    """
    trouve = _BIB_RE.match(cle)
    return trouve.group(1) if trouve else ""


def _temps_ou_vide(brut: str) -> str:
    """Temps normalisé. **`00:00:00` vaut temps absent** — un DNF sort avec cette
    valeur (La Baule 2022, EPP Arnaud) et la laisser ferait basculer
    `mapping.derive_status` sur « finisher »."""
    brut = (brut or "").strip()
    if brut in ("—", "-", "--"):
        return ""
    normalise = normalize_time(brut)
    return "" if normalise in ("", "00:00:00") else normalise


def _genre(categorie: str) -> str:
    """Préfixe M/F de la catégorie fédérale (`MS2`, `FV1`, `MHAN`, `MT1`)."""
    initiale = (categorie or "").strip()[:1].upper()
    return initiale if initiale in ("M", "F") else ""


def _est_relais(epreuve: str) -> bool:
    """Déduit du slug d'épreuve. Non vérifié sur données réelles (§8.3 du design) :
    aucune épreuve équipe sondée n'a de classement publié."""
    return heat_is_relay(epreuve) or _EQUIPE_RE.search(epreuve.lower()) is not None


def _titre(soup) -> str:
    """L'en-tête de résultats : le `<title>`, à défaut un `<h1>` qui le porte."""
    candidats = [soup.title.get_text(" ", strip=True)] if soup.title else []
    candidats += [h1.get_text(" ", strip=True) for h1 in soup.find_all("h1")]
    return next((texte for texte in candidats if _norm(texte).startswith("resultats")), "")


def _entete(soup, evenement: str, epreuve: str) -> tuple[str, date | None]:
    """(nom d'épreuve, date), lus indépendamment dans l'en-tête (`_titre`).

    Le nom est déjà qualifié par l'épreuve (« - M ») : pas de `qualify_event_name`.
    """
    titre = _titre(soup)
    trouve = _RE_NOM.search(titre)
    if trouve:
        nom = trouve.group(1)
    else:
        nom = f"{evenement} {epreuve}".replace("-", " ").title()
        logger.warning(
            "Titre fftri illisible (%r) : nom d'épreuve replié sur les slugs (%s)", titre, nom
        )
    event_date = None
    jour = _RE_DATE.search(titre)
    if jour:
        try:
            event_date = date(int(jour.group(3)), int(jour.group(2)), int(jour.group(1)))
        except ValueError:
            logger.warning("Date d'édition fftri illisible : %r", jour.group(0))
    else:
        logger.warning("Date d'édition absente du titre fftri : %r", titre)
    return nom, event_date


def _construire(
    ligne: dict,
    *,
    source_url: str,
    evenement: str,
    epreuve: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    chrono: tuple[str, str],
) -> ScrapedResult:
    """Une carte de classement → un participant.

    Les rangs par genre et par catégorie ne figurent plus sur la liste : ils se
    lisent sur la fiche, chargée pour les seuls membres du club (`scrape_event_all`).
    Les recalculer depuis l'ordre de la liste s'écarte d'une place au-delà de
    quelques centaines de lignes (mesuré, #898).
    """
    nom, prenom = split_athlete_name(ligne.get("nom", ""))
    cle = _cle_fiche(ligne.get("details_href", ""))
    categorie = ligne.get("cat", "")
    clt = ligne.get("clt", "")

    result = ScrapedResult(source_url=source_url, provider="t2area")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date
    result.athlete_name = nom
    result.athlete_firstname = prenom
    result.club = ligne.get("club", "")
    result.category = categorie
    genre = ligne.get("genre", "")
    result.gender = genre if genre in ("M", "F") else _genre(categorie)
    result.bib_number = _dossard(cle)
    result.rank_overall = normalize_rank(clt)
    result.total_time = _temps_ou_vide(ligne.get("temps", ""))
    # La place porte le statut quand elle ne porte pas de rang (DNF, DSQ).
    result.status = derive_status_from_label(clt)
    result.is_relay = _est_relais(epreuve)
    _appliquer_splits(result, [(libelle, _temps_ou_vide(temps)) for libelle, temps in ligne.get("splits", [])])
    # De quoi diagnostiquer sans re-scraper : clé brute, ligue, chronométreur.
    result.raw_data = {
        "cle_fiche": cle,
        "fiche_url": ligne.get("details_href", ""),
        "clt": clt,
        "temps": ligne.get("temps", ""),
        "league": ligne.get("league", ""),
        "chronometreur": chrono[0],
        "chronometreur_url": chrono[1],
        "evenement": evenement,
        "epreuve": epreuve,
    }
    # La FFTRI publie parfois un temps sur ses disqualifiés (ALLARD Pierre,
    # `42:23:00` sur La Baule 2022 — une aberration de saisie côté source).
    # Invariant du dépôt, partagé avec wiclax/sportinnovation/raceresult/
    # timepulse : un non-finisher n'a ni temps total ni rang.
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.total_time = ""
        result.rank_overall = None
        result.rank_category = None
        result.rank_gender = None
    return result


_RE_CHRONO = re.compile(r"r[ée]sultats\s+produits\s+par", re.I)


def _chronometreur(soup) -> tuple[str, str]:
    """(nom, lien) du chronométreur amont : « Résultats produits par X »."""
    for p in soup.find_all("p"):
        texte = p.get_text(" ", strip=True)
        if not _RE_CHRONO.search(texte):
            continue
        lien = p.find("a", href=True)
        if lien:
            return lien.get_text(" ", strip=True), lien["href"].strip()
        return _RE_CHRONO.sub("", texte).strip(), ""
    return "", ""


def _avertir_source_amont(nom: str, lien: str, url: str) -> None:
    """Journalise quand le chronométreur amont est un provider **supporté**.

    La FFTRI ne chronomètre pas, elle republie : à la source, on aurait les
    dossards de tout le monde et les splits de tous les participants. Cette
    délégation ne peut pas être automatisée — la mention ne lie que la page
    d'accueil du chronométreur, jamais l'épreuve, et aucun identifiant d'épreuve
    n'est récupérable (§1.1 du design). L'opérateur reste seul à pouvoir fournir
    l'URL source.

    Import local de `registry` : `registry` importe ce module au chargement,
    l'inverse au niveau module créerait un cycle (même procédé que les helpers
    Klikego appelés depuis `registry`).
    """
    if not lien:
        return
    from app.scrapers.registry import detect_provider

    provider = detect_provider(lien)
    if not provider:
        return
    logger.warning(
        "%s : résultats produits par %s (%s) — le provider « %s » est supporté et "
        "sa source est plus riche (dossards et splits de tous les participants). "
        "L'URL d'épreuve n'est pas déductible de cette page : à fournir à la main.",
        url, nom or provider, lien, provider,
    )


def _parse_edition(
    html: str, source_url: str, evenement: str, epreuve: str
) -> list[ScrapedResult]:
    """HTML d'une édition → participants. **Pur** : aucune requête.

    Aucune carte sur une page qui n'est pas une redirection (`_fetch_edition`
    l'a déjà écartée) : le markup a changé, et mieux vaut une erreur qu'un
    classement vide importé en silence.
    """
    soup = BeautifulSoup(html, "lxml")
    cartes = soup.select("article.edition-result")
    if not cartes:
        raise ValueError(
            f"Aucun classement (article.edition-result) sur {source_url} : "
            "markup fftri modifié."
        )
    event_name, event_date = _entete(soup, evenement, epreuve)
    # Le type vient du **slug d'épreuve**, vérifié sur les slugs réels :
    # `swim-run-m` → swimrun-m, `triathlon-xs-jeunes` → triathlon-xs,
    # `bike-run-s-open-eq` → bike-run.
    event_type = classify_event_type(epreuve)
    chrono = _chronometreur(soup)
    _avertir_source_amont(chrono[0], chrono[1], source_url)
    return [
        _construire(
            _ligne(carte),
            source_url=source_url,
            evenement=evenement,
            epreuve=epreuve,
            event_name=event_name,
            event_type=event_type,
            event_date=event_date,
            chrono=chrono,
        )
        for carte in cartes
    ]


# Libellé de split normalisé → slot positionnel de ScrapedResult. Les libellés
# **changent selon le sport** (triathlon : Natation / T1 / Vélo / T2 / Course à
# Pied ; duathlon : CàP 1 / T1 / Vélo / T2 / CàP 2), d'où un mapping par libellé
# et jamais par position : un mapping positionnel rangerait le 3ᵉ segment d'un
# aquathlon (Natation / T1 / CàP) dans le vélo.
_SLOTS = {
    "natation": "swim_time",
    "cap 1": "swim_time",
    "t1": "t1_time",
    "transition 1": "t1_time",
    "velo": "bike_time",
    "t2": "t2_time",
    "transition 2": "t2_time",
    "course a pied": "run_time",
    "cap 2": "run_time",
}

_RANGS_FICHE = {"sexe": "rank_gender", "categorie": "rank_category"}


def _parse_fiche(html: str) -> dict[str, int]:
    """Rangs officiels d'une fiche individuelle : `{"rank_gender": …, "rank_category": …}`.

    Le bandeau porte « 453 Global », « 419 Sexe », « 89 Catégorie » : la liste
    ne publie plus que le rang global.
    """
    soup = BeautifulSoup(html, "lxml")
    rangs: dict[str, int] = {}
    for bloc in soup.select(".rd-rank"):
        mots = bloc.get_text(" ", strip=True).split()
        if len(mots) < 2:
            continue
        champ = _RANGS_FICHE.get(_norm(mots[-1]))
        rang = normalize_rank(mots[0])
        if champ and rang is not None:
            rangs[champ] = rang
    return rangs


def _appliquer_splits(result: ScrapedResult, segments: list[tuple[str, str]]) -> None:
    """Range les segments dans les 5 slots, ou bascule **tout** sur `segments`.

    Filet : un seul libellé hors table suffit à basculer sur la liste ordonnée
    étiquetée, déplafonnée et prioritaire dans `mapping.build_splits`. Rien n'est
    perdu silencieusement sur un sport au découpage inattendu, et le cas nominal
    garde les clés canoniques que le front sait afficher.
    """
    ranges: dict[str, str] = {}
    for libelle, temps in segments:
        slot = _SLOTS.get(_norm(libelle))
        if slot is None:
            result.segments = [(lib, tps) for lib, tps in segments if tps]
            return
        if temps:
            ranges[slot] = temps
    for slot, temps in ranges.items():
        setattr(result, slot, temps)


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants d'une **édition**. Un appel = une `Course`.

    Les splits de tous les participants sont sur la liste. Les rangs par genre
    et par catégorie, eux, ne sont que sur la fiche individuelle, soit une
    requête par participant : ils ne sont chargés que pour les lignes dont le
    club passe `core.club.is_tcn`. Coût mesuré sur La Baule M 2022 : 25 requêtes
    (1 classement + 24 membres TCN sur 901 lignes), borné par l'effectif du
    club. Le scraper devient conscient du club, mais **réutilise** la définition
    unique de `core/club.py` (règle de #76).

    Chaque `ScrapedResult` porte `source_url` = l'URL **soumise** par l'appelant.
    C'est cette URL qui devient `Course.source_url` (clé de cache TTL), pas
    l'URL canonique de l'édition à laquelle elle est tronquée : si le Sheet
    donne une URL de fiche, l'idempotence tient à cette troncature répétée
    par ce scraper, pas à une réécriture de la clé stockée.
    """
    evenement, epreuve, annee = _parse_url(url)
    with http.client(timeout=30, headers=HEADERS) as client:
        if not annee:
            annee = _resolve_annee(client, evenement, epreuve)
        edition_url = _edition_url(evenement, epreuve, annee)
        resultats = _parse_edition(
            _fetch_edition(client, edition_url), edition_url, evenement, epreuve
        )
        for resultat in resultats:
            resultat.source_url = url
        membres_tcn = 0
        fiches = 0
        for resultat in resultats:
            if not is_tcn(resultat.club) or resultat.status:
                continue
            membres_tcn += 1
            brut = resultat.raw_data.get("fiche_url") or ""
            if not brut:
                continue
            # `urljoin` + contrôle de host : un lien de fiche relatif ne doit ni
            # suivre un chemin résolu contre le mauvais host, ni lever une
            # exception masquée par l'`except` ci-dessous.
            fiche_url = urljoin(BASE_URL, brut)
            if (urlparse(fiche_url).hostname or "").lower() != HOST:
                continue
            try:
                html = _fetch(client, fiche_url)
            except httpx.HTTPError as exc:
                # Une fiche qui tombe ne doit pas emporter l'épreuve entière.
                logger.warning("Fiche fftri %s ignorée : %s", fiche_url, exc)
                continue
            for champ, rang in _parse_fiche(html).items():
                setattr(resultat, champ, rang)
            fiches += 1
    logger.info(
        "fftri.t2area.com : %d participants sur %s (%d membre(s) TCN classé(s), "
        "%d fiche(s) chargée(s))",
        len(resultats), edition_url, membres_tcn, fiches,
    )
    return resultats

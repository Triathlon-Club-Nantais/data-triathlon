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

Flux (cf. docs/superpowers/specs/2026-07-26-t2area-scraper-design.md) :
  1. `_parse_url`      → (événement, épreuve, année) ; une fiche est tronquée
                         vers son édition (le cas réel du Sheet)
  2. `_resolve_annee`  → année absente : 1 GET sur l'épreuve, on prend la plus récente
  3. `_fetch`          → GET du classement
  4. `_parse_edition`  → `<table id="resultList">` → N `ScrapedResult`
  5. `_parse_fiche`    → pour les **seules** lignes `is_tcn` : GET de la fiche,
                         accordéon → splits (25 requêtes sur La Baule, pas 901)
"""
import logging
import re
from datetime import date
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.club import is_tcn

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .classify import classify_event_type
from .utils import derive_status_from_label, normalize_rank, normalize_time, split_athlete_name

logger = logging.getLogger(__name__)

BASE_URL = "https://fftri.t2area.com"
HOST = "fftri.t2area.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_PREFIXE = "/calendrier/"
_ANNEE_RE = re.compile(r"^\d{4}$")

_ACCENTS = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _norm(text: str) -> str:
    """Minuscule, sans accents, espaces aplatis. « Détails » → « details »."""
    sans_accents = (text or "").strip().lower().translate(_ACCENTS)
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
    """GET simple. Une édition inexistante répond **303 vers l'accueil**, donc 200 :
    c'est l'absence de `#resultList` qui la démasque (cf. `_parse_edition`)."""
    response = client.get(url)
    response.raise_for_status()
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


# Libellé d'en-tête normalisé → clé logique de colonne. L'en-tête réel porte
# **10** colonnes (`id_league` et `league` s'intercalent entre `Clt/CAT` et
# `Détails`) : lire par position ferait prendre la ligue pour le lien de fiche.
# Stable sur les 5 éditions sondées, de 2022 à 2026.
_COLONNES = {
    "clt": "clt",
    "clt/f": "clt_f",
    "temps": "temps",
    "nom": "nom",
    "club": "club",
    "cat": "cat",
    "clt/cat": "clt_cat",
    "id_league": "id_league",
    "league": "league",
    "details": "details",
}

#: Colonnes sans lesquelles une ligne n'a pas de sens.
_COLONNES_REQUISES = frozenset({"clt", "temps", "nom"})

_BIB_RE = re.compile(r"^bib-(\d+)$", re.I)

# Marqueurs d'équipe dans le **slug d'épreuve** (`swim-run-m-eq`, `triathlon-relais`).
# Jetons isolés : le « eq » de « equipe » ne doit pas être capté par accident.
_RELAIS_RE = re.compile(r"(?<![a-z0-9])(eq|relais|duo)(?![a-z0-9])")

# Le <h1> porte tout l'en-tête :
#   « Résultats du Triathlon de La Baule - M - 2022 - édition du 18-09-2022 »
# Deux regex **indépendantes** : un libellé inattendu ne doit pas faire perdre la
# date, qui entre dans l'identité de la Course (UNIQUE(name, event_date, event_type)).
_RE_NOM = re.compile(r"r[ée]sultats\s+d[eu]s?\s+(.+?)\s+-\s+\d{4}\s+-\s+[ée]dition\b", re.I)
_RE_DATE = re.compile(r"[ée]dition\s+du\s+(\d{2})-(\d{2})-(\d{4})", re.I)


def _index_colonnes(table) -> dict[str, int]:
    """Clé logique → position, lue dans les libellés du `<thead>`."""
    index: dict[str, int] = {}
    for position, th in enumerate(table.select("thead th")):
        cle = _COLONNES.get(_norm(th.get_text(" ", strip=True)))
        if cle and cle not in index:
            index[cle] = position
    return index


def _href(cellule) -> str:
    lien = cellule.find("a", href=True)
    return lien["href"].strip() if lien else ""


def _lignes(table, index: dict[str, int]) -> list[dict[str, str]]:
    """Une ligne = {clé de colonne → texte}, plus les href de Détails et Club.

    Une ligne trop courte est une anomalie de markup : journalisée et sautée
    plutôt que lue de travers.
    """
    attendu = max(index.values()) + 1
    lignes: list[dict[str, str]] = []
    for tr in table.select("tbody tr"):
        cellules = tr.find_all("td")
        if len(cellules) < attendu:
            logger.warning(
                "Ligne fftri ignorée : %d cellules pour %d colonnes", len(cellules), attendu
            )
            continue
        ligne = {
            cle: cellules[position].get_text(" ", strip=True)
            for cle, position in index.items()
        }
        ligne["details_href"] = _href(cellules[index["details"]]) if "details" in index else ""
        ligne["club_href"] = _href(cellules[index["club"]]) if "club" in index else ""
        lignes.append(ligne)
    return lignes


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
    sur l'appariement par athlète (`import_service._match_without_bib`).
    """
    trouve = _BIB_RE.match(cle)
    return trouve.group(1) if trouve else ""


def _temps_ou_vide(brut: str) -> str:
    """Temps normalisé. **`00:00:00` vaut temps absent** — un DNF sort avec cette
    valeur (La Baule 2022, EPP Arnaud) et la laisser ferait basculer
    `mapping.derive_status` sur « finisher »."""
    normalise = normalize_time((brut or "").strip())
    return "" if normalise in ("", "00:00:00") else normalise


def _genre(categorie: str) -> str:
    """Préfixe M/F de la catégorie fédérale (`MS2`, `FV1`, `MHAN`, `MT1`)."""
    initiale = (categorie or "").strip()[:1].upper()
    return initiale if initiale in ("M", "F") else ""


def _est_relais(epreuve: str) -> bool:
    """Déduit du slug d'épreuve. Non vérifié sur données réelles (§8.3 du design) :
    aucune épreuve équipe sondée n'a de classement publié."""
    return _RELAIS_RE.search(epreuve.lower()) is not None


def _titre(soup) -> str:
    """Texte du `<h1>` de résultats (la page en porte d'autres, décoratifs)."""
    for h1 in soup.find_all("h1"):
        texte = h1.get_text(" ", strip=True)
        if _norm(texte).startswith("resultats"):
            return texte
    return ""


def _entete(soup, evenement: str, epreuve: str) -> tuple[str, date | None]:
    """(nom d'épreuve, date), lus indépendamment dans le `<h1>`.

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
    ligne: dict[str, str],
    *,
    source_url: str,
    evenement: str,
    epreuve: str,
    event_name: str,
    event_type: str,
    event_date: date | None,
    chrono: tuple[str, str],
) -> ScrapedResult:
    """Une ligne de classement → un participant."""
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
    result.gender = _genre(categorie)
    result.bib_number = _dossard(cle)
    result.rank_overall = normalize_rank(clt)
    result.rank_gender = normalize_rank(ligne.get("clt_f", ""))
    result.rank_category = normalize_rank(ligne.get("clt_cat", ""))
    result.total_time = _temps_ou_vide(ligne.get("temps", ""))
    # La colonne Clt porte le statut quand elle ne porte pas de rang (DNF, DQ).
    result.status = derive_status_from_label(clt)
    result.is_relay = _est_relais(epreuve)
    # De quoi diagnostiquer sans re-scraper : clé brute, ligue, lien club, chronométreur.
    result.raw_data = {
        "cle_fiche": cle,
        "fiche_url": ligne.get("details_href", ""),
        "clt": clt,
        "temps": ligne.get("temps", ""),
        "id_league": ligne.get("id_league", ""),
        "league": ligne.get("league", ""),
        "club_href": ligne.get("club_href", ""),
        "chronometreur": chrono[0],
        "chronometreur_url": chrono[1],
        "evenement": evenement,
        "epreuve": epreuve,
    }
    # La FFTRI publie parfois un temps sur ses disqualifiés (ALLARD Pierre,
    # `42:23:00` sur La Baule 2022 — une aberration de saisie côté source).
    # Invariant du dépôt, partagé avec wiclax/sportinnovation/raceresult/timepulse :
    # un non-finisher n'a pas de temps total.
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.total_time = ""
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
    if provider == "playwright":
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
    """HTML d'une édition → participants. **Pur** : aucune requête."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find(id="resultList")
    if table is None:
        raise ValueError(
            f"Aucun classement (#resultList) sur {source_url} : édition inexistante "
            "— le site redirige alors vers son accueil — ou markup fftri modifié."
        )
    index = _index_colonnes(table)
    manquantes = _COLONNES_REQUISES - set(index)
    if manquantes:
        raise ValueError(
            f"En-tête fftri inattendu sur {source_url} : "
            f"colonnes manquantes {sorted(manquantes)}."
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
            ligne,
            source_url=source_url,
            evenement=evenement,
            epreuve=epreuve,
            event_name=event_name,
            event_type=event_type,
            event_date=event_date,
            chrono=chrono,
        )
        for ligne in _lignes(table, index)
    ]


# Libellé d'accordéon normalisé → slot positionnel de ScrapedResult. Les libellés
# **changent selon le sport** (triathlon : Natation / … / Course à Pied ;
# duathlon : CàP 1 / … / CàP 2), d'où un mapping par libellé et jamais par
# position : un mapping positionnel rangerait le 3ᵉ segment d'un aquathlon
# (Natation / T1 / CàP) dans le vélo.
_SLOTS = {
    "natation": "swim_time",
    "cap 1": "swim_time",
    "transition 1": "t1_time",
    "velo": "bike_time",
    "transition 2": "t2_time",
    "course a pied": "run_time",
    "cap 2": "run_time",
}


def _parse_fiche(html: str) -> list[tuple[str, str]]:
    """Segments (libellé, temps) de l'accordéon d'une fiche individuelle.

    « Général » est écarté : c'est le temps total, déjà lu dans le classement.
    Un segment à `00:00:00` ressort à "" (cf. `_temps_ou_vide`).
    """
    soup = BeautifulSoup(html, "lxml")
    segments: list[tuple[str, str]] = []
    for item in soup.select("ul.accordion li.accordion__item"):
        titres = [t.get_text(" ", strip=True) for t in item.select("button .title")]
        if len(titres) < 2:
            continue
        libelle, temps = titres[0], titres[1]
        if _norm(libelle) == "general":
            continue
        segments.append((libelle, _temps_ou_vide(temps)))
    return segments


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

    Les splits ne sont chargés que pour les lignes dont le club passe
    `core.club.is_tcn` : ils vivent sur la fiche individuelle, soit une requête
    par participant. Coût mesuré sur La Baule M 2022 : 25 requêtes (1 classement
    + 24 membres TCN sur 901 lignes) — borné par l'effectif du club, pas par la
    taille de l'épreuve. Le scraper devient conscient du club, mais **réutilise**
    la définition unique de `core/club.py` (règle de #76).

    `source_url` est l'URL **canonique** de l'édition, même si l'appel est parti
    d'une fiche individuelle : les deux désignent le même classement, et la forme
    canonique rend le `rescrape-db` suivant idempotent.
    """
    evenement, epreuve, annee = _parse_url(url)
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if not annee:
            annee = _resolve_annee(client, evenement, epreuve)
        edition_url = _edition_url(evenement, epreuve, annee)
        resultats = _parse_edition(_fetch(client, edition_url), edition_url, evenement, epreuve)
        fiches = 0
        for resultat in resultats:
            if not is_tcn(resultat.club):
                continue
            fiche_url = resultat.raw_data.get("fiche_url") or ""
            if not fiche_url:
                continue
            try:
                html = _fetch(client, fiche_url)
            except httpx.HTTPError as exc:
                # Une fiche qui tombe ne doit pas emporter l'épreuve entière.
                logger.warning("Fiche fftri %s ignorée : %s", fiche_url, exc)
                continue
            _appliquer_splits(resultat, _parse_fiche(html))
            fiches += 1
    logger.info(
        "fftri.t2area.com : %d participants sur %s (%d fiche(s) TCN chargée(s))",
        len(resultats), edition_url, fiches,
    )
    return resultats

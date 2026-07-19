"""
Moteur RaceResult générique — issue #50.

Couvre trois façades d'un même produit, toutes alimentées par la même API JSON
publique (aucun Playwright, la page RRPublish est un SPA qui n'apporte rien de
plus) :

  - `my*.raceresult.com`      — RaceResult direct, l'eventId est dans le path ;
  - `espace-competition.com`  — front RaceResult, `new RRPublish(el, <id>, …)` ;
  - `chronoconsult.fr`        — façade WordPress au-dessus de RaceResult.

Chaînage d'appels (établi par sondage réel le 2026-07-18) :
  1. GET /{eventId}/RRPublish/data/config?page=results
  2. GET /{eventId}/RRPublish/data/list?key=…&listname=…&contest=N&r=all
     → **301** vers /{eventId}/results/list : `follow_redirects=True` obligatoire.
  3. La date d'épreuve n'est dans aucun des deux : elle vit dans le JSON-LD
     schema.org de la page /{eventId}/results.
"""
import json
import logging
import re
from datetime import date as date_t
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .classify import classify_event_type
from .utils import (
    derive_status_from_label,
    normalize_rank,
    normalize_time,
    qualify_event_name,
    split_athlete_name,
)

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}

# Racine par défaut quand l'URL d'entrée est une façade tierce : toutes les
# façades sondées pointent leurs assets vers my.raceresult.com.
_API_DEFAUT = "https://my.raceresult.com"

# `RRPublish(document.getElementById("divRRPublish"),  399938 , 'results')` — les
# espaces autour de l'argument sont fréquents et doivent être tolérés.
_RE_RRPUBLISH = re.compile(r"RRPublish\s*\([^,]+,\s*(\d+)\s*,")
# Repli : le logo de l'épreuve est servi par l'API et porte le même id.
_RE_LOGO = re.compile(r"raceresult\.com/(\d+)/api/logo")


def _api_base(url: str) -> str:
    """Racine HTTPS de l'API RaceResult à interroger pour cette URL.

    Un host `my*.raceresult.com` est déjà la bonne racine (les épreuves sont
    réparties sur plusieurs serveurs : my, my2, my3…). Toute autre façade est
    servie depuis la racine par défaut.
    """
    host = (urlparse(url).netloc or "").lower()
    if host == "raceresult.com" or host.endswith(".raceresult.com"):
        return f"https://{host}"
    return _API_DEFAUT


def _resolve_event_id(url: str, client: httpx.Client) -> str:
    """Identifiant d'épreuve RaceResult désigné par l'URL.

    Sur un host RaceResult, c'est le premier segment numérique du path — zéro
    requête. Sur une façade, une seule page est téléchargée : l'id se lit dans
    l'appel `new RRPublish(...)`, avec repli sur l'URL du logo. Le `comp_uid` des
    URLs `espace-competition.com` est délibérément ignoré : c'est un identifiant
    interne au front, pas la clé de données.
    """
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    if host == "raceresult.com" or host.endswith(".raceresult.com"):
        for segment in parsed.path.strip("/").split("/"):
            if segment.isdigit():
                return segment
        raise ValueError(f"Aucun identifiant d'épreuve dans l'URL RaceResult : {url}")

    resp = client.get(url, headers=HEADERS)
    resp.raise_for_status()
    for motif in (_RE_RRPUBLISH, _RE_LOGO):
        trouve = motif.search(resp.text)
        if trouve:
            return trouve.group(1)
    raise ValueError(
        f"Identifiant d'épreuve RaceResult introuvable dans la page : {url}"
    )


def _json_ld_event(html: str) -> dict:
    """Premier bloc JSON-LD de type Event de la page, `{}` si aucun.

    Le bloc peut être un objet seul, une liste d'objets, ou un `@graph` — on
    balaie les trois formes plutôt que de parier sur une seule.
    """
    soup = BeautifulSoup(html, "lxml")
    for balise in soup.find_all("script", type="application/ld+json"):
        try:
            charge = json.loads(balise.string or "")
        except (ValueError, TypeError):
            continue
        candidats = charge if isinstance(charge, list) else [charge]
        if isinstance(charge, dict) and isinstance(charge.get("@graph"), list):
            candidats = charge["@graph"]
        for noeud in candidats:
            if isinstance(noeud, dict) and noeud.get("@type") == "Event":
                return noeud
    return {}


def _fetch_meta(
    event_id: str, base: str, client: httpx.Client
) -> tuple[str, "date_t | None", str]:
    """(nom d'épreuve, date, ville) depuis le JSON-LD de la page /results.

    C'est la **seule** source de la date : l'API `config` comme l'API `list` n'en
    portent aucune. Une page sans JSON-LD exploitable renvoie des valeurs vides
    plutôt que de lever : l'épreuve reste importable, le nom retombera sur
    `config["eventname"]` et la date sur `None`.
    """
    try:
        resp = client.get(f"{base}/{event_id}/results", headers=HEADERS)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("RaceResult %s : page /results illisible (%s)", event_id, exc)
        return "", None, ""

    noeud = _json_ld_event(resp.text)
    if not noeud:
        return "", None, ""

    jour = None
    brut = str(noeud.get("startDate") or "")
    if brut:
        try:
            jour = date_t.fromisoformat(brut[:10])
        except ValueError:
            logger.warning("RaceResult %s : startDate illisible (%r)", event_id, brut)

    adresse = (noeud.get("location") or {}).get("address") or {}
    ville = str(adresse.get("addressLocality") or "")
    return str(noeud.get("name") or ""), jour, ville


def _fetch_config(event_id: str, base: str, client: httpx.Client) -> dict:
    """Config publique de l'épreuve : `key`, `contests`, `lists`, `splits`."""
    resp = client.get(
        f"{base}/{event_id}/RRPublish/data/config",
        params={"page": "results"},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


# Clés qui marquent une feuille dans l'arbre `lists` (une liste réelle, pas un
# groupe intermédiaire).
_CLES_FEUILLE = ("Contest", "Name", "ID")


def _iter_list_specs(config: dict) -> list[tuple[str, str]]:
    """Listes exploitables : [(listname, indice de contest), …].

    `config["lists"]` est un arbre dont le chemin, joint par `|`, forme le
    `listname` attendu par l'API. On aplatit récursivement : une feuille est un
    nœud non-dict, ou un dict portant une clé de description (`Contest`,
    `Name`, `ID`). L'indice de contest n'est qu'un **indice** — il est vérifié
    empiriquement à l'appel (cf. `_contest_candidates`).
    """
    specs: list[tuple[str, str]] = []

    def descendre(noeud, chemin: list[str]) -> None:
        if not isinstance(noeud, dict) or any(c in noeud for c in _CLES_FEUILLE):
            indice = noeud.get("Contest") if isinstance(noeud, dict) else None
            specs.append(("|".join(chemin), "" if indice is None else str(indice)))
            return
        for cle, valeur in noeud.items():
            descendre(valeur, [*chemin, str(cle)])

    for cle, valeur in (config.get("lists") or {}).items():
        descendre(valeur, [str(cle)])
    return specs


_ACCENTS = str.maketrans("àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ", "aaaeeeeiioouuucAAAEEEEIIOOUUUC")

# Enrobages d'affichage posés par RaceResult autour de l'expression réelle.
_RE_ENROBAGE = re.compile(r"^(ucase|lcase|OuStatut|Statut|if)\s*\(", re.IGNORECASE)
# Décorations de cellule : `[img:https://…]` en préfixe, `#` de `"#" & [BIB]`.
_RE_IMG = re.compile(r"\[img:[^\]]*\]")


def _peel(expr: str) -> str:
    """Expression RaceResult ramenée à sa forme comparable.

    Pèle les enrobages d'affichage (`ucase(…)`, `OuStatut(…)`, `if(…;X;…)`), les
    crochets et le `#`, puis met en minuscules sans accents. `ucase([CLUB])` et
    `[Club]` convergent ainsi vers `club`, ce qui permet une table de motifs
    courte au lieu d'une énumération de variantes.
    """
    s = (expr or "").strip()
    while True:
        trouve = _RE_ENROBAGE.match(s)
        if not trouve or not s.endswith(")"):
            break
        s = s[trouve.end():-1].strip()
    # Une expression conditionnelle garde son premier terme utile.
    if ";" in s:
        s = max(s.split(";"), key=len).strip()
    s = s.replace("#", "").replace("[", "").replace("]", "")
    return s.translate(_ACCENTS).lower().strip()


def _clean_cell(brut) -> str:
    """Cellule débarrassée de ses décorations d'affichage."""
    if brut is None:
        return ""
    return _RE_IMG.sub("", str(brut)).strip().lstrip("#").strip()


_RE_RANG_CAT = re.compile(r"^(\d+)\.\s*(.*)$")


def _split_rank_category(cell: str) -> tuple[int | None, str]:
    """Sépare `"1.S4M"` en (rang catégorie, catégorie).

    L'expression `#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]` colle les deux
    dans une seule colonne. Une cellule sans préfixe numérique est une catégorie
    nue (cas des non-finishers, qui n'ont pas de rang).
    """
    cell = _clean_cell(cell)
    trouve = _RE_RANG_CAT.match(cell)
    if trouve:
        return int(trouve.group(1)), trouve.group(2).strip()
    return None, cell


def _role(peeled: str) -> str:
    """Rôle sémantique d'une expression pelée, "" si non reconnu.

    Ordre des tests significatif : les rangs sont testés en premier, car une
    expression suffixée `.p` / `.overall.p` est **toujours** un rang, jamais un
    temps. Sans cette règle, `[Natation.OVERALL.P]` (« 2. ») passerait pour le
    temps de natation, qui vit dans la colonne suivante.
    """
    if "classementgeneral" in peeled:
        return "rang"
    if "agegroup" in peeled or "classementcategorie" in peeled:
        return "rang_categorie"
    if peeled.endswith(".p"):
        return "rang_de_split"  # colonne à écarter
    if any(motif in peeled for motif in ("affichernom", "nomrelais", "nomequipe")):
        return "nom"
    if "club" in peeled:
        return "club"
    if peeled in ("sexemf", "sex", "sexe", "gender"):
        return "sexe"
    if peeled in ("time", "tempstotal", "tempscorrige", "finish", "arrivee"):
        return "temps"
    return ""


def _map_columns(
    payload: dict,
) -> tuple[dict[str, int], list[tuple[str, int]], dict[str, int]]:
    """(rôles, segments, extras) — l'index de chaque colonne du payload.

    Étage 1, l'index : `col = DataFields.index(Field.Expression)`, l'algorithme
    exact de `RRPublish.js`. `DataFields` préfixe toujours `BIB` et `ID`, qui
    n'ont pas d'entrée dans `Fields` — la position dans `Fields` est donc
    décalée et inutilisable telle quelle. Le dossard, lui, vient de
    `DataFields.index("BIB")` et ne passe par aucune heuristique.

    Étage 2, le rôle : cf. `_role`. Un champ dont l'expression est un token nu
    entre crochets (`[Natation]`) et sans suffixe de rang est un **segment**,
    étiqueté par son `Label`. Tout le reste part en extras → `raw_data`.
    """
    data_fields = [str(e) for e in payload.get("DataFields") or []]
    index_par_expr = {expr: i for i, expr in enumerate(data_fields)}

    roles: dict[str, int] = {}
    segments: list[tuple[str, int]] = []
    extras: dict[str, int] = {}

    if "BIB" in index_par_expr:
        roles["bib"] = index_par_expr["BIB"]

    for champ in payload.get("Fields") or []:
        expr = str(champ.get("Expression") or "")
        col = index_par_expr.get(expr)
        if col is None:
            logger.debug("RaceResult : champ sans colonne de données (%r)", expr)
            continue
        peeled = _peel(expr)
        role = _role(peeled)
        if role == "rang_de_split":
            continue
        if role:
            roles.setdefault(role, col)
            continue
        label = str(champ.get("Label") or "").strip()
        # Segment : token nu entre crochets, donc sans point de qualification.
        if "[" in expr and "." not in peeled and label:
            segments.append((label, col))
        else:
            extras[expr] = col

    # La catégorie partage la colonne du rang de catégorie (cellule « 1.S4M »).
    if "rang_categorie" in roles:
        roles.setdefault("categorie", roles["rang_categorie"])
    return roles, segments, extras


_RE_PREFIXE_GROUPE = re.compile(r"^#\d+_")


def _strip_group_prefix(cle: str) -> str:
    """Retire le préfixe d'ordonnancement d'une clé de groupe (`#1_Distance M`)."""
    return _RE_PREFIXE_GROUPE.sub("", str(cle)).strip()


def _iter_groups(data: dict) -> list[tuple[str, str, list]]:
    """[(libellé contest, libellé statut, lignes), …] depuis le dict `data`.

    `data` est imbriqué à deux niveaux : le groupe de niveau 1 identifie le
    **contest** (`#1_Distance M`), celui de niveau 2 le **statut**
    (`#1_` = finishers, `#2_Abandons` = DNF, `#3_Non Partants` = DNS). Certains
    payloads n'ont qu'un niveau ; les deux formes sont acceptées.
    """
    groupes: list[tuple[str, str, list]] = []
    for cle_contest, contenu in (data or {}).items():
        contest = _strip_group_prefix(cle_contest)
        if isinstance(contenu, dict):
            for cle_statut, lignes in contenu.items():
                if isinstance(lignes, list):
                    groupes.append((contest, _strip_group_prefix(cle_statut), lignes))
        elif isinstance(contenu, list):
            groupes.append((contest, "", contenu))
    return groupes


_NON_FINISHERS = (STATUS_DNF, STATUS_DNS, STATUS_DSQ)


def _build_result(
    ligne: list,
    roles: dict[str, int],
    segments: list[tuple[str, int]],
    extras: dict[str, int],
    *,
    source_url: str,
    event_name: str,
    event_date,
    contest_label: str,
    status_label: str,
) -> ScrapedResult:
    """Construit un `ScrapedResult` depuis une ligne de données RaceResult."""

    def cellule(role: str) -> str:
        col = roles.get(role)
        if col is None or col >= len(ligne):
            return ""
        return _clean_cell(ligne[col])

    nom_qualifie = qualify_event_name(event_name, contest_label)
    r = ScrapedResult(
        source_url=source_url,
        provider="raceresult",
        bib_number=cellule("bib"),
        event_name=nom_qualifie,
        event_date=event_date,
        event_type=classify_event_type(nom_qualifie),
    )

    nom, prenom = split_athlete_name(cellule("nom"))
    r.athlete_name, r.athlete_firstname = nom, prenom
    r.club = cellule("club")
    r.gender = cellule("sexe")
    r.rank_category, r.category = _split_rank_category(cellule("categorie"))
    r.total_time = normalize_time(cellule("temps"))
    r.is_relay = any(
        mot in contest_label.lower() for mot in ("relais", "relay", "equipe", "équipe")
    )

    # La cellule de rang porte le rang **ou** le statut (`OuStatut(…)`).
    cellule_rang = cellule("rang")
    r.rank_overall = normalize_rank(cellule_rang)

    # Deux signaux concordants, le groupe primant sur la cellule : un groupe
    # « Abandons » qualifie toute la tranche, la cellule ne renseigne que les
    # payloads sans sous-groupe de statut.
    r.status = (
        derive_status_from_label(status_label)
        or derive_status_from_label(cellule_rang)
        or ""
    )

    r.segments = [
        (label, normalize_time(_clean_cell(ligne[col])))
        for label, col in segments
        if col < len(ligne) and _clean_cell(ligne[col])
    ] or None

    r.raw_data = {
        expr: _clean_cell(ligne[col]) for expr, col in extras.items() if col < len(ligne)
    }

    # Nettoyage systématique de la maison (cf. wiclax.py) : un non-finisher n'a
    # ni temps total ni rang, quoi qu'annonce le payload.
    if r.status in _NON_FINISHERS:
        r.total_time = ""
        r.rank_overall = r.rank_category = r.rank_gender = None
    elif r.total_time:
        r.status = r.status or "finisher"

    return r


def _contest_candidates(indice: str, contests: dict) -> list[str]:
    """Contests à essayer pour une liste, dans l'ordre le plus probable.

    `contest=0` (« tous ») n'est pas universel : sur certaines épreuves il
    répond 404 sur toutes les listes et il faut interroger contest par contest,
    chacun livrant son propre payload. On essaie donc l'indice annoncé par la
    config s'il est significatif, puis `0`, puis chaque contest déclaré.
    """
    candidats: list[str] = []
    if indice and indice != "0":
        candidats.append(indice)
    candidats.append("0")
    candidats.extend(str(c) for c in (contests or {}))
    vus: set[str] = set()
    return [c for c in candidats if not (c in vus or vus.add(c))]


def _fetch_list(
    event_id: str,
    base: str,
    key: str,
    listname: str,
    contest: str,
    client: httpx.Client,
) -> dict | None:
    """Payload d'une liste pour un contest donné, `None` si indisponible.

    La route répond **301** vers `/{eventId}/results/list` : le client doit être
    ouvert avec `follow_redirects=True`, sinon la réponse est vide. Un 404 (liste
    non servie pour ce contest, ou liste morte) est journalisé en `debug` et
    renvoie `None` — le balayage continue.
    """
    resp = client.get(
        f"{base}/{event_id}/RRPublish/data/list",
        params={
            "key": key,
            "listname": listname,
            "page": "results",
            "contest": contest,
            "r": "all",
        },
        headers=HEADERS,
    )
    if resp.status_code == 404:
        logger.debug(
            "RaceResult %s : liste %r absente pour contest=%s", event_id, listname, contest
        )
        return None
    resp.raise_for_status()
    try:
        payload = resp.json()
    except ValueError:
        logger.debug("RaceResult %s : liste %r non JSON", event_id, listname)
        return None
    if not isinstance(payload, dict) or not payload.get("data"):
        return None
    return payload


def _richness(r: ScrapedResult) -> int:
    """Nombre de champs renseignés — arbitre les doublons entre listes."""
    champs = (
        r.athlete_name, r.athlete_firstname, r.club, r.category, r.gender, r.total_time
    )
    return (
        sum(1 for c in champs if c)
        + len(r.segments or [])
        + sum(1 for v in r.raw_data.values() if v)
    )


def _prefer(nouveau: ScrapedResult, ancien: ScrapedResult) -> bool:
    """Vrai si `nouveau` doit remplacer `ancien` dans la fusion par clé.

    Un statut non-finisher (DNF/DNS/DSQ) est un signal fort qui ne doit pas
    être écrasé par une ligne simplement plus riche en colonnes mais muette
    sur le statut — cas d'une même personne présente dans une seconde liste
    sans sous-groupe de statut (I2). Mais ce signal ne doit jouer que face à
    une ligne concurrente qui n'a elle-même **aucun temps d'arrivée réel** :
    un chrono est un signal plus fort qu'un statut annoncé. Sans cette
    seconde garde, un statut non-finisher devenait inconditionnel et pouvait
    détruire un finisher réel — une liste « Non Partants » figée à la veille
    (dossard réattribué, engagé finalement présent) écrasait alors temps,
    rang et club corrects (N1, régression du garde-fou I2).
    """
    if nouveau.status in _NON_FINISHERS and not ancien.total_time:
        return True
    if ancien.status in _NON_FINISHERS and not nouveau.total_time:
        return False
    return _richness(nouveau) > _richness(ancien)


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Importe tous les participants d'une épreuve RaceResult.

    Balaie **toutes** les listes exploitables et fusionne : une liste
    « Individuel » et une liste « Relais » se complètent au lieu de s'écraser.
    Borne réseau : `len(lists) × (1 + len(contests))` requêtes au pire, ~5 en pratique.
    """
    base = _api_base(url)
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        event_id = _resolve_event_id(url, client)
        config = _fetch_config(event_id, base, client)
        key = str(config.get("key") or "")
        contests = config.get("contests") or {}
        nom_meta, jour, _ville = _fetch_meta(event_id, base, client)
        event_name = nom_meta or str(config.get("eventname") or "")

        specs = _iter_list_specs(config)
        # Clé de fusion (contest, dossard) : deux contests peuvent porter le même
        # dossard, c'est précisément le cas que la qualification par contest règle.
        fusion: dict[tuple[str, str], ScrapedResult] = {}
        for listname, indice in specs:
            for contest in _contest_candidates(indice, contests):
                payload = _fetch_list(event_id, base, key, listname, contest, client)
                if payload is None:
                    continue
                roles, segments, extras = _map_columns(payload)
                data = payload.get("data") or {}
                groupes = _iter_groups(data)
                # `contest=0` (« tous ») peut, sur certaines épreuves, renvoyer un
                # payload **plat et non nommé** au lieu du sous-découpage par
                # contest vu sur Rumilly (`#1_Distance M` / `#2_Abandons`…) : les
                # lignes de plusieurs contests distincts s'y retrouvent mélangées
                # sans qu'aucun signal (ni la clé de groupe, ni `contests`) ne
                # permette de les rattacher chacune au bon contest. Le seul repli
                # qui restait — `listname`, constant sur tout le payload — ne
                # règle pas ce cas : deux lignes du même dossard (une par contest
                # réel) y collisionnent encore (N2 / #21, au-delà de la collision
                # *entre* listes qu'I3 réglait déjà). Pire, quand la même tranche
                # est exposée par deux chemins de listes différents, ce repli
                # produit alors deux « Courses » distinctes pour les mêmes
                # athlètes (I3 a échangé une collision contre une duplication).
                # Dans ce cas ambigu, ce payload n'est donc pas exploité : on ne
                # `break` pas, le balayage continue contest par contest — chacun
                # devient alors étiquetable via `contests.get(contest)`, seule
                # source de contest fiable ici, et convergera vers la même clé
                # de fusion quel que soit le chemin de liste qui y a mené (ce qui
                # résout la duplication en même temps que la collision).
                ambigu = (
                    contest == "0"
                    and len(contests) > 1
                    and bool(groupes)
                    and not any(label for label, _statut, _lignes in groupes)
                )
                if not ambigu:
                    for contest_label, status_label, lignes in groupes:
                        # Le nom de contest vient de la clé de groupe, avec repli
                        # sur la table `contests` de la config, puis sur le
                        # `listname`, puis sur le contest brut en dernier
                        # recours : la clé de fusion doit rester injective même
                        # quand le payload ne nomme rien (groupe non nommé servi
                        # avec un contest absent de la table `contests`, cf. I3
                        # / issue #21).
                        libelle = (
                            contest_label
                            or str(contests.get(contest) or "")
                            or listname
                            or contest
                        )
                        for ligne in lignes:
                            r = _build_result(
                                ligne, roles, segments, extras,
                                source_url=url,
                                event_name=event_name,
                                event_date=jour,
                                contest_label=libelle,
                                status_label=status_label,
                            )
                            if not r.bib_number:
                                continue
                            cle = (libelle, r.bib_number)
                            ancien = fusion.get(cle)
                            if ancien is None or _prefer(r, ancien):
                                fusion[cle] = r
                if contest == "0" and not ambigu:
                    # contest=0 (« tous ») livre déjà l'ensemble des contests dans
                    # un seul payload : inutile de tenter les autres candidats.
                    # Un contest spécifique, lui, ne livre QUE sa propre tranche
                    # (cf. docstring `_contest_candidates`) — le balayage doit donc
                    # continuer sur les contests suivants, faute de quoi ils sont
                    # silencieusement perdus (C1). Un payload ambigu ne compte
                    # pas comme une réponse exploitée : le balayage doit
                    # continuer pour aller chercher les payloads spécifiques.
                    break

    if not fusion:
        essayees = ", ".join(nom for nom, _ in specs) or "aucune liste déclarée"
        raise ValueError(
            f"Épreuve RaceResult {event_id} : aucune liste exploitable "
            f"(listes essayées : {essayees})."
        )
    return list(fusion.values())

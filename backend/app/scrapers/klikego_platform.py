"""
Moteur partagé pour la plateforme Klikego / Breizh Chrono.

Les deux fournisseurs utilisent le même back-office. Leur page de résultats
charge l'intégralité de la liste (finishers + DNF/DNS/DSQ) dans une iframe
`/bc/resultats/course-result.jsp` qui embarque les données dans un
`<script id="data">` encodé base64 + XOR (clé 'K'). C'est la source de vérité,
contrairement à `/v8/evenement/resultats-search.jsp` qui n'expose que les
classés et sous-pagine.

Format d'une ligne (séparateur `|`), 12 champs :
  dossard|diploma|classement|classementCat|nom|cat|sexe|club_ou_ville|inter|officiel|reel|endurance
"""
import base64
import re
from datetime import date as _date
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .utils import normalize_time, strip_accents

_XOR_KEY = ord("K")
_PAGE_SIZE = 50

# Les deux fronts terminent le <title> par «  - {code postal} - {ville} » ; ce
# marqueur borne le nom de l'épreuve, qui peut lui-même contenir des « - »
# (« Triathlon d'Angers - Entre Loire et Maine 2026 »).
_TITLE_LOCATION_RE = re.compile(r"\s-\s\d{5}\s-\s")

# Formes d'équipe **constatées** dans les heats de la plateforme, chacune vue
# sur un événement réel :
#   relais  — `triathlon-s-relais`, `duathlon-s---en-relais`
#   duo     — `swim-run-m-duo` (Mesquer 2026), `swimrun-court-duo` (Dinard 2025)
#   binome  — `format-s---en-binome` (RE SwimRun 2025), face à `format-m---en-solo`
#   equipe  — `duathlon-liffre-cormier-clm-par-equipe` (CLM par équipes)
# Toutes désignent une épreuve courue à plusieurs, donc un relais au sens du
# modèle. Cette liste ne s'élargit **que** sur constat : « team », « paire »,
# « trio » n'ont jamais été observés dans un heat, les ajouter au ressenti
# reclasserait des épreuves sur une hypothèse.
_TEAM_HEAT_WORDS = frozenset({"relais", "duo", "binome", "equipe"})

# Le slug est tokenisé par tirets, le libellé affiché par espaces : on découpe
# sur tout ce qui n'est ni lettre ni chiffre pour comparer des mots entiers.
# Les accents tombent d'abord — le slug les aplatit (`en-binome`) mais pas le
# libellé (« En Binôme », « CLM par Équipe »), et « ô » couperait le mot en deux.
_WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def heat_is_relay(*signals: str) -> bool:
    """Le heat désigne-t-il une épreuve d'équipe ? (`is_relay` du modèle)

    Un heat de la plateforme est mono-discipline et mono-format : le drapeau est
    une propriété du heat, pas du participant. Les signaux acceptés sont son
    slug et son libellé affiché, dans n'importe quel ordre — l'un ou l'autre
    manque selon le chemin d'import (un heat ciblé directement n'a pas de
    libellé).

    Le mot compte comme mot et non comme sous-chaîne : « arduo » n'est pas un
    duo. Se tromper ne se voit pas à l'affichage, mais `is_relay` entre dans
    l'identité de la `Course` (UNIQUE `name, event_date, event_type, is_relay`) :
    deux heats homonymes fusionnent, et le classement mélange équipes et solos
    (#203, #295).
    """
    for signal in signals:
        words = set(_WORD_SPLIT_RE.split(strip_accents(signal or "").lower()))
        if words & _TEAM_HEAT_WORDS:
            return True
    return False


def decode_data_block(html: str) -> list[list[str]]:
    """Décode le `<script id="data">` d'une page course-result.jsp.

    Retourne une liste de lignes, chaque ligne = liste de ses champs (str).
    `[]` si le bloc est absent ou vide.
    """
    el = BeautifulSoup(html, "lxml").find(id="data")
    if not el:
        return []
    raw_b64 = el.get_text().strip()
    if not raw_b64:
        return []
    try:
        raw = base64.b64decode(raw_b64)
        text = bytes(b ^ _XOR_KEY for b in raw).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        # HTML externe : un bloc corrompu ne doit pas faire échouer l'import.
        return []
    return [line.split("|") for line in text.split("\n") if line.strip()]


def _slugify(text: str) -> str:
    """« Triathlon M individuel » → « triathlon-m-individuel » (forme des heats)."""
    plain = strip_accents(text)
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def parse_event_name(html: str, heat: str = "") -> str:
    """Nom de l'épreuve lu dans le `<title>` de la page de résultats.

    C'est la seule source fiable : le slug de l'URL perd les accents, les
    esperluettes et la casse (« Run  Bike De Fay De Bretagne »), et une URL
    `coureur.jsp` n'en porte aucun. Deux gabarits, un par front :

      Klikego : « {épreuve} - {code postal} - {ville} - Résultats | Klikego »
      BC      : « Résultats {libellé du heat} - {épreuve} - {code postal} - {ville} »

    Renvoie `""` si le titre ne situe pas d'épreuve (page générique de
    `coureur.jsp`) : mieux vaut pas de nom qu'un faux nom, l'appelant repliera.
    """
    soup = BeautifulSoup(html, "lxml")
    if not soup.title:
        return ""
    title = re.sub(r"\s+", " ", soup.title.get_text()).strip()

    loc = _TITLE_LOCATION_RE.search(title)
    if not loc:
        # Sans « - {code postal} - », le titre ne parle pas d'une épreuve précise.
        return ""
    name = title[: loc.start()].strip()
    name = re.sub(r"^R[ée]sultats\s+", "", name)

    # BC préfixe le nom par le libellé du heat, dont le slug est le heat lui-même.
    if heat:
        parts = name.split(" - ")
        for i in range(1, len(parts)):
            if _slugify(" - ".join(parts[:i])) == _slugify(heat):
                return " - ".join(parts[i:]).strip()
    return name


_STATUS_BY_TOKEN = {
    "DNF": STATUS_DNF,
    "AB": STATUS_DNF,
    "ABANDON": STATUS_DNF,
    "DNS": STATUS_DNS,
    "NP": STATUS_DNS,
    "DSQ": STATUS_DSQ,
    "DQ": STATUS_DSQ,
    "DISQ": STATUS_DSQ,
}


def _split_name(full: str) -> tuple[str, str]:
    """`"DE POORTER Axel"` -> ("DE POORTER", "Axel"). Nom = tokens MAJUSCULES de tête."""
    parts = full.split()
    i = 0
    while i < len(parts) and parts[i].isupper():
        i += 1
    return " ".join(parts[:i]), " ".join(parts[i:])


def _parse_rank(value: str) -> int | None:
    m = re.match(r"\d+", value.strip())
    return int(m.group(0)) if m else None


def parse_data_row(fields: list[str]) -> dict:
    """Transforme une ligne du data block (12 champs) en dict de champs ScrapedResult."""
    f = (fields + [""] * 12)[:12]
    # `gender_raw` = champ `sexe` du data block (cf. docstring du module) ; on
    # le normalise en `gender` ("M"/"F"), le nom utilisé côté modèle.
    dossard, _diploma, clt, cltcat, nom, cat, gender_raw, club, _inter, officiel, _reel, _end = f

    status = _STATUS_BY_TOKEN.get(clt.strip().upper(), "")
    nom_fam, prenom = _split_name(nom.strip())
    gender = gender_raw.strip().upper()
    if gender == "H":  # alias utilisé par certains systèmes
        gender = "M"

    return {
        "bib_number": dossard.strip(),
        "athlete_name": nom_fam,
        "athlete_firstname": prenom,
        "category": cat.strip(),
        "gender": gender if gender in ("M", "F") else "",
        "club": club.strip(),
        "rank_overall": None if status else _parse_rank(clt),
        "rank_category": None if status else _parse_rank(cltcat),
        "total_time": "" if status == STATUS_DNS else normalize_time(officiel.strip()),
        "status": status,
    }


def _course_result_url(base: str, event_id: str, heat: str, inter: str, page: int) -> str:
    query = urlencode(
        {
            "ref": event_id,
            "heat": heat,
            "query": "",
            "category": "",
            "sex": "",
            "inter": inter,
            "page": page,
        }
    )
    return f"{base}/bc/resultats/course-result.jsp?{query}"


def fetch_heat_rows(
    base: str, event_id: str, heat: str, client: httpx.Client, inter: str = ""
) -> list[list[str]]:
    """Pagine course-result.jsp et retourne toutes les lignes brutes (dédoublonnées)."""
    out: dict[str, list[str]] = {}
    page = 0
    prev_first: str | None = None
    while True:
        resp = client.get(_course_result_url(base, event_id, heat, inter, page))
        if resp.status_code != 200:
            break
        rows = decode_data_block(resp.text)
        if not rows:
            break
        first_bib = rows[0][0] if rows[0] else ""
        if first_bib and first_bib == prev_first:
            break  # la plateforme répète la dernière page
        prev_first = first_bib
        for r in rows:
            bib = r[0] if r else ""
            if bib and bib not in out:
                out[bib] = r
        if len(rows) < _PAGE_SIZE:
            break
        page += 1
    return list(out.values())


def discover_inter_options(heat_page_html: str) -> list[tuple[str, str]]:
    """Retourne les checkpoints (value, label) du <select name="inter">, sauf 'Arrivée'."""
    sel = BeautifulSoup(heat_page_html, "lxml").find("select", {"name": "inter"})
    if not sel:
        return []
    out = []
    for opt in sel.find_all("option"):
        value = (opt.get("value") or "").strip()
        if value:
            out.append((value, opt.get_text(strip=True)))
    return out


# Mapping label de checkpoint -> slot positionnel ScrapedResult.
# Ordre : motifs spécifiques (numérotés) avant génériques.
_INTER_SLOT_RULES = [
    ("course à pied 1", "swim"),
    ("course a pied 1", "swim"),
    ("cap 1", "swim"),
    ("course à pied 2", "run"),
    ("course a pied 2", "run"),
    ("cap 2", "run"),
    ("natation", "swim"),
    ("nat", "swim"),
    ("t1", "t1"),
    ("vélo", "bike"),
    ("velo", "bike"),
    ("bike", "bike"),
    ("t2", "t2"),
    ("course", "run"),
    ("cap", "run"),
    ("run", "run"),
]


def inter_label_to_slot(label: str) -> str | None:
    """Mappe un label de checkpoint (`"Natation + T1"`, `"Vélo"`…) vers un slot."""
    low = label.lower()
    for key, slot in _INTER_SLOT_RULES:
        if key in low:
            return slot
    return None


def fetch_inter_splits(
    base: str,
    event_id: str,
    heat: str,
    inter_options: list[tuple[str, str]],
    client: httpx.Client,
) -> dict[str, dict[str, str]]:
    """Collecte les temps de checkpoints pour tous les participants.

    Pour chaque option `inter` mappable sur un slot, pagine le data block et lit
    le champ `inter` (idx 8). Retourne `{bib: {slot: "HH:MM:SS"}}`.
    Les checkpoints dont le label ne mappe sur aucun slot sont ignorés.
    """
    out: dict[str, dict[str, str]] = {}
    for value, label in inter_options:
        slot = inter_label_to_slot(label)
        if slot is None:
            continue
        for row in fetch_heat_rows(base, event_id, heat, client, inter=value):
            f = (row + [""] * 12)[:12]
            bib, inter_time = f[0].strip(), normalize_time(f[8].strip())
            if bib and inter_time:
                out.setdefault(bib, {})[slot] = inter_time
    return out


def build_heat_results(
    *,
    base: str,
    provider: str,
    event_id: str,
    heat: str,
    heat_page_html: str,
    event_name: str,
    slug: str,
    event_type: str,
    source_url: str,
    event_date: _date | None,
    client: httpx.Client,
) -> list[ScrapedResult]:
    """Assemble la liste complète d'un heat (finishers + DNF/DNS/DSQ) avec splits inter."""
    rows = fetch_heat_rows(base, event_id, heat, client)
    inter_options = discover_inter_options(heat_page_html)
    splits = fetch_inter_splits(base, event_id, heat, inter_options, client) if inter_options else {}

    # Le nom porté par la page prime sur celui dérivé du slug d'URL (accents,
    # casse, esperluette) ; le slug reste le repli quand la page n'en donne pas.
    event_name = parse_event_name(heat_page_html, heat) or event_name

    # Le drapeau relais est une propriété du heat, propagée à tous ses résultats
    # (cf. `heat_is_relay`). Ici seul le slug est connu ; Breizh Chrono surécrit
    # ensuite la valeur en y ajoutant le libellé (`_detect_relay`), le patron
    # reste correct : la deuxième écriture prime.
    relay_heat = heat_is_relay(heat)

    results: list[ScrapedResult] = []
    for raw in rows:
        d = parse_data_row(raw)
        r = ScrapedResult(source_url=source_url, provider=provider)
        r.event_name = event_name
        r.event_type = event_type
        r.event_date = event_date
        r.is_relay = relay_heat
        r.bib_number = d["bib_number"]
        r.athlete_name = d["athlete_name"]
        r.athlete_firstname = d["athlete_firstname"]
        r.category = d["category"]
        r.gender = d["gender"]
        r.club = d["club"]
        r.rank_overall = d["rank_overall"]
        r.rank_category = d["rank_category"]
        r.total_time = d["total_time"]
        r.status = d["status"]
        r.raw_data["heat_slug"] = heat
        for slot, t in splits.get(d["bib_number"], {}).items():
            setattr(r, f"{slot}_time", t)
        results.append(r)
    return results

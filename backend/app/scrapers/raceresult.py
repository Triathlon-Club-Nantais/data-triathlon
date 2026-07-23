"""
Moteur RaceResult générique — issue #50.

Couvre trois façades d'un même produit, toutes alimentées par la même API JSON
publique (aucun Playwright, la page RRPublish est un SPA qui n'apporte rien de
plus) :

  - `my*.raceresult.com`      — RaceResult direct, l'eventId est dans le path ;
  - `espace-competition.com`  — front RaceResult, `new RRPublish(el, <id>, …)` ;
  - `chronoconsult.fr`        — même front, mais l'id est servi **entre
    guillemets** (`new RRPublish(el, "392745", …)`).

Chaînage d'appels — cf. `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`,
qui fait foi (9 épreuves, 3 façades) :

  1. GET https://my.raceresult.com/{eventId}/results/config?page=results
     → `key`, `contests`, et surtout `TabConfig.Lists` : un tableau plat d'une
       entrée par couple (liste, contest), le contest étant **explicite**.
  2. GET https://my.raceresult.com/{eventId}/results/list
         ?key=…&listname=…&contest=N&page=results
  3. La date d'épreuve n'est dans aucun des deux : elle vit dans le JSON-LD
     schema.org de la page /{eventId}/results.

Deux pièges qui ont coûté une revue de branche entière, et qu'il ne faut pas
réintroduire :

  - La route `/{eventId}/RRPublish/data/…` est un **alias hérité**. Elle répond
    404 sur toute épreuve de la saison en cours. Le 301 qu'elle émettait vers
    `/results/` était l'indice.
  - `my.raceresult.com` (l'apex, **sans chiffre**) sert toutes les épreuves, y
    compris celles que l'interface héberge sur `my2`/`my3`/`my4`. Aucune
    résolution de serveur n'est nécessaire.
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

# Racine unique de l'API. Vérifiée sur les 9 épreuves du panel de sondage, dont
# des épreuves servies par l'interface depuis my2/my3/my4 : l'apex les sert
# toutes en 200, sans redirection. Les façades tierces chargent d'ailleurs
# elles-mêmes `//my.raceresult.com/RRPublish/load.js.php`.
_API_BASE = "https://my.raceresult.com"

# `new RRPublish(document.getElementById("divRRPublish"), 411749, "results")` sur
# espace-competition.com, mais `…, "392745", …` sur chronoconsult.fr : les
# guillemets autour de l'identifiant sont **optionnels**. Sans cette tolérance,
# aucune épreuve chronoconsult n'est résolvable.
_RE_RRPUBLISH = re.compile(r"""RRPublish\s*\([^,]+,\s*["']?(\d+)["']?\s*,""")
# Repli : le logo de l'épreuve est servi par l'API et porte le même id.
_RE_LOGO = re.compile(r"raceresult\.com/(\d+)/api/logo")


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
    event_id: str, client: httpx.Client
) -> tuple[str, date_t | None, str]:
    """(nom d'épreuve, date, ville) depuis le JSON-LD de la page /results.

    C'est la **seule** source de la date : l'API `config` comme l'API `list` n'en
    portent aucune. Confirmé sur les 9 épreuves du panel. Une page sans JSON-LD
    exploitable renvoie des valeurs vides plutôt que de lever : l'épreuve reste
    importable, le nom retombera sur `config["eventname"]` et la date sur `None`.
    """
    try:
        resp = client.get(f"{_API_BASE}/{event_id}/results", headers=HEADERS)
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


def _fetch_config(event_id: str, client: httpx.Client) -> dict:
    """Config publique de l'épreuve : `key`, `contests`, `TabConfig`, `splits`."""
    resp = client.get(
        f"{_API_BASE}/{event_id}/results/config",
        params={"page": "results"},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


def _lists_or_raise(config: dict) -> list[dict]:
    """Entrées bien formées de `TabConfig.Lists`, ou `ValueError`.

    Une `TabConfig.Lists` absente ou de mauvaise forme trahit l'interrogation
    de la route héritée `/{id}/RRPublish/data/…` (cf. en-tête du module). Garde
    partagée par la sélection publiée et la sélection `hidden` (#60).
    """
    lists = (config.get("TabConfig") or {}).get("Lists")
    if not isinstance(lists, list):
        raise ValueError(
            f"TabConfig.Lists de forme inattendue : {type(lists)!r} "
            "(route héritée interrogée par erreur ?)"
        )
    return [item for item in lists if isinstance(item, dict) and item.get("Name")]


def _iter_list_specs(config: dict) -> list[tuple[str, str]]:
    """Listes publiées : [(listname, contest), …].

    Les listes vivent sous `config["TabConfig"]["Lists"]` : un **tableau plat**,
    une entrée par couple (liste, contest), chacune portant son `Name` complet
    (`"04 - Classements|Classement général"` — le `|` est un séparateur
    d'affichage posé par RaceResult, pas une hiérarchie à reconstruire) et son
    `Contest` **explicite**. `config["lists"]` vaut `null` sur cette route : le
    contest n'a donc rien à résoudre empiriquement, contrairement à ce que
    faisait la première version de ce module.

    Écarte les listes `Mode == "hidden"`. Sur le panel, `Mode != "hidden"`
    couvre les contests de façon quasi exhaustive (13/13 sur Genève, 4/4 sur
    Rumilly).

    `Mode` sépare ce que l'organisateur a choisi de publier, **pas** le
    classement de l'affichage : sur 406211 les deux sont même inversés — les 13
    listes publiées y sont des listes d'affichage LIVE, et le seul vrai
    classement, celui qui porte les splits, est `hidden`.

    Élargir aux listes `hidden` en repli a donc été prototypé, et mesuré sur
    cette épreuve : le classement `hidden` y est en `Contest="0"` et indexe ses
    contests sous d'autres libellés (`'PTS5 Men'`) que les listes publiées
    (`'Finish'`, `'Run - Start'`). La fusion par clé `(libellé, dossard)` n'y
    trouve **aucune** clé commune — 37 doublons s'ajoutent aux 42 participants,
    soit 79 lignes et autant de `Course` fantômes.

    Ce chiffre établit un **préalable** (réconcilier les libellés de contest),
    pas une impossibilité. La sélection n'a pas eu à bouger ici, le trou de
    temps de 406211 se réglant en amont dans `_role` (cf.
    `_RE_TEMPS_RESULTAT_TEXTE`) ; une épreuve qui exigerait vraiment les listes
    `hidden` reste à instruire.

    Ne PAS revenir au critère `Live` : il avait été calibré sur une seule
    épreuve, où il coïncidait. Sur l'event 405100 les 10 listes portent `Live=1`,
    y compris les 3 vrais classements — le filtre y vide l'épreuve entière.
    `Format` ne discrimine pas davantage.
    """
    return [
        (str(item.get("Name")), str(item.get("Contest") or "0"))
        for item in _lists_or_raise(config)
        if item.get("Mode") != "hidden"
    ]


def _iter_hidden_list_specs(config: dict) -> list[tuple[str, str]]:
    """Listes `hidden` : [(listname, contest), …], matière de l'enrichissement (#60).

    Symétrique de `_iter_list_specs`. Ces listes n'introduisent ni participant
    ni contest (cf. design #60) : elles ne font qu'enrichir, par dossard, un
    participant déjà établi par une liste publiée. On les prend **toutes**,
    indépendamment du `Name` (banni comme qualifiant, §3) et du `Contest` — le
    tri du grain (splits) et de l'ivraie (inscrits, colonnes vides, classement
    redondant) se fait à l'exécution, par la valeur des cellules. Une liste sans
    apport reste inerte.
    """
    return [
        (str(item.get("Name")), str(item.get("Contest") or "0"))
        for item in _lists_or_raise(config)
        if item.get("Mode") == "hidden"
    ]


_ACCENTS = str.maketrans("àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ", "aaaeeeeiioouuucAAAEEEEIIOOUUUC")

# Enrobages d'affichage posés par RaceResult autour de l'expression réelle.
_RE_ENROBAGE = re.compile(
    r"^(ucase|lcase|trim|format|OuStatut|Statut|iif|if|switch)\s*\(", re.IGNORECASE
)
# Terme purement littéral (`"#"` dans `"#"&[BIB]`) : décoration, pas la valeur.
_RE_LITTERAL = re.compile(r'^"[^"]*"$')
# Expression réduite à un token simple : `Natation`, `[Vélo]`, `Transition1`.
# Un point, une parenthèse ou un espace signalent une expression qualifiée
# (`Natation.OVERALL.p`) ou calculée, jamais un segment de course.
_RE_TOKEN_SIMPLE = re.compile(r"^[a-z0-9_]+$")
# Une durée : `19:46`, `1:05:07`, `20:27:34.12`. Sert à qualifier les **valeurs**
# d'une colonne candidate au rôle de segment. `normalize_time` est permissif et
# laisse passer `107` (un nombre de tours) ou `447.795` (des kilomètres) : sans
# ce filtre, une colonne « Tours » ou « Distance » atterrissait dans `splits`.
_RE_DUREE = re.compile(r"^\d{1,3}:\d{2}(:\d{2})?([.,]\d+)?$")
# Forme canonique rendue par `normalize_time` quand elle **reconnaît** une durée
# (`HH:MM:SS`, heures sur 2 chiffres ou plus) ; elle rend son entrée inchangée
# sinon. Tester la sortie contre ce motif est donc « `normalize_time` a reconnu
# la valeur » — garde plus large que `_RE_DUREE`, qui rejette `1h23'45` alors
# que `normalize_time` le lit. C'est la garde du rôle `temps` (issue #62), dont
# une cellule peut porter un statut (`OuStatut([Temps])`) et non une durée.
_RE_DUREE_NORMALISEE = re.compile(r"^\d{2,}:\d{2}:\d{2}$")
# Décorations de cellule : `[img:https://…]` en préfixe, `#` de `"#" & [BIB]`.
_RE_IMG = re.compile(r"\[img:[^\]]*\]")
# Un terme qui compare n'est pas la valeur affichée mais la condition qui la
# choisit : `[STATUS]<>2`, `[SEX]="f"`, `[Relais]=1`.
_RE_COMPARAISON = re.compile(r"(<>|>=|<=|=|<|>)")


def _split_profondeur(s: str, sep: str) -> list[str]:
    """Découpe `s` sur `sep`, en ignorant les séparateurs entre parenthèses.

    `if([Relais]=1;switch(a;b);[AfficherNom])` doit se couper en trois termes,
    pas en cinq : le `;` interne au `switch(...)` appartient à ce dernier. Une
    découpe naïve tronquait l'expression et faisait perdre la colonne.
    """
    parties: list[str] = []
    courant: list[str] = []
    profondeur = 0
    for car in s:
        if car == "(":
            profondeur += 1
        elif car == ")":
            profondeur -= 1
        if car == sep and profondeur == 0:
            parties.append("".join(courant))
            courant = []
        else:
            courant.append(car)
    parties.append("".join(courant))
    return parties


# Borne de sécurité pour la boucle de point fixe de `_peel` : sur les formules
# réellement observées (jusqu'à 3 imbrications), le point fixe est atteint en
# 2-3 tours. Cette borne n'est là que pour garantir la terminaison si une
# formule inédite oscillait — elle ne doit jamais être atteinte en pratique.
_PEEL_MAX_ITERATIONS = 10


def _peel(expr: str) -> str:
    """Expression RaceResult ramenée à sa forme comparable.

    Trois formes se superposent en production, et doivent être défaites dans cet
    ordre à **chaque tour** :

    1. **La concaténation** `X & iif(…)` colle un rang au libellé
       (`"M (1.)"`, `"M0M (1.)"`). Seul le premier terme porte la valeur. Elle
       se traite en premier : `ucase([SEX]) & iif(…)` commence par un enrobage
       *et* se termine par `)`, si bien qu'un dépelage préalable avalerait toute
       l'expression et la corromprait.
    2. **Les enrobages d'affichage** (`ucase(…)`, `OuStatut(…)`, `if(…)`,
       `switch(…)`, `trim(…)`).
    3. **Les conditionnelles** `if(cond;valeur)` : l'enveloppe
       `if([STATUS]<>2;[X])` est omniprésente sur les épreuves récentes. Le
       terme utile n'est pas le plus long — c'est celui qui **ne compare pas**.
       Retenir le plus long tout court sélectionnait `[STATUS]<>2` et faisait
       perdre tous les segments de Genève et Besançon.

    Cet ordre reste le bon *au sein d'un tour*, mais une seule passe ne suffit
    pas : une concaténation peut être **imbriquée dans** un `if(…)`
    (`if([STATUS]<>2;[Vélo] & " (" & [Vélo.OVERALL.P] & ")")`), auquel cas
    l'étape 1 ne la voit pas (profondeur > 0 au premier tour) et ne serait
    jamais rejouée après l'étape 3 qui vient de l'exposer. `_peel` boucle donc
    sur les trois étapes jusqu'à un **point fixe** (la chaîne cesse de changer),
    borné par `_PEEL_MAX_ITERATIONS` pour garantir la terminaison même sur une
    formule inédite qui ne convergerait pas.

    `ucase([CLUB])` et `[Club]` convergent ainsi vers `club`, ce qui permet une
    table de motifs courte au lieu d'une énumération de variantes.
    """
    s = (expr or "").strip()

    for _ in range(_PEEL_MAX_ITERATIONS):
        avant = s

        # 1. Concaténation : la valeur est portée par le premier terme non
        # littéral. `"#"&[BIB]` commence par une décoration ; retenir `"#"`
        # produisait une expression vide qui finissait classée en segment sous
        # son étiquette « N° ».
        termes = [t.strip() for t in _split_profondeur(s, "&")]
        if len(termes) > 1:
            utiles = [t for t in termes if t and not _RE_LITTERAL.match(t)]
            s = (utiles or termes)[0].strip()

        # 2. Enrobages d'affichage, en pelures successives.
        while True:
            trouve = _RE_ENROBAGE.match(s)
            if not trouve or not s.endswith(")"):
                break
            s = s[trouve.end():-1].strip()

        # 3. Conditionnelle : on écarte les termes qui comparent.
        termes = [t.strip() for t in _split_profondeur(s, ";") if t.strip()]
        if len(termes) > 1:
            valeurs = [t for t in termes if not _RE_COMPARAISON.search(t)] or termes
            s = max(valeurs, key=len).strip()

        if s == avant:
            break
    else:
        # Point fixe non atteint en `_PEEL_MAX_ITERATIONS` tours : jamais vu en
        # production (cf. note de robustesse ci-dessus), mais si une formule
        # inédite oscillait un jour, la chaîne partiellement pelée retournée
        # ici serait sinon corrompue sans aucune trace pour le diagnostiquer.
        logger.debug(
            "RaceResult : _peel n'a pas convergé en %d tours, arrêt sur %r",
            _PEEL_MAX_ITERATIONS, s,
        )

    s = s.replace("#", "").replace("[", "").replace("]", "")
    return s.translate(_ACCENTS).lower().strip()


# Enrobage i18n complet, **sans accolade interne** : `{DE:Startnr|EN:Bib}`.
# Le `[^{}]*` (plutôt qu'un `.*` gourmand) est ce qui empêche `"{A:1} et {B:2}"`
# d'être vu comme un seul enrobage et amputé en `"1} et {B:2"`.
_RE_LABEL_I18N = re.compile(r"^\{([^{}]*)\}$")
# Une variante, et le format d'une **clé de langue** : exactement deux lettres.
# Cette ancre est la garde utile, car `_label_i18n` sert aussi aux cellules
# (cf. `_clean_cell`), donc à du texte libre saisi par les organisateurs, où un
# deux-points est banal. Sans elle, `"{Team: Bleu}"` devenait `" Bleu"` et
# `"{ATTENTION: dossard 12}"` devenait `" dossard 12"` : la partie gauche,
# pourtant porteuse de sens, était prise pour un code de langue et jetée.
#
# **Deux lettres, ni plus ni moins** — et non « 2 à 3 », ni une énumération
# fermée `FR|EN|DE|…`. Les trois options ont été pesées sur la mesure : les 266
# clés relevées sur le panel sont toutes de longueur 2 (`EN` 103, `FR` 103,
# `DE` 60), ce qui est aussi la forme d'ISO 639-1.
#
#   - « 2 à 3 » laissait passer `"{Nom:Dupont}"` → `"Dupont"` et
#     `"{Cat:S4M}"` → `"S4M"` : des cellules légitimes amputées en silence.
#     Les deux contre-exemples sont de longueur 3, donc fermés ici.
#   - Une énumération fermée fermerait le même axe, mais coûterait cher en
#     portée **à cause de la règle « toutes les parties bien formées »** : une
#     seule langue non listée (`{DE:…|EN:…|CS:…}`) désarmerait l'enrobage
#     entier et rendrait la valeur brute. Or RaceResult est un produit allemand
#     à diffusion européenne, et le panel contient déjà des épreuves
#     internationales (Tour of Hellas, World Triathlon Para Cup) où une langue
#     hors liste est plausible.
#
# La longueur fixe ferme les deux contre-exemples connus sans fermer aucune
# langue : elle domine les deux autres options sur les faits relevés. Le risque
# résiduel — une clé de langue à 3 lettres (ISO 639-2, `"{GER:…}"`) qui ne
# serait pas dépelée — est une erreur **bruyante et réversible** (valeur brute
# visible en UI), pas une amputation muette.
_RE_VARIANTE_I18N = re.compile(r"^([A-Za-z]{2}):(.*)$", re.DOTALL)


def _label_i18n(label: str) -> str:
    """Étiquette débarrassée de son enrobage i18n `{DE:…|EN:…|FR:…}`.

    Les épreuves internationales encodent leurs libellés dans les trois langues
    (`{DE:Startnr|EN:Bib|FR:Dos.}`) : sans normalisation, ce brut atterrit tel
    quel comme clé JSON de `segments` / `raw_data`. Priorité à `FR:`, repli sur
    `EN:`, puis sur la première variante non vide ; une étiquette sans cet
    enrobage traverse inchangée.

    Sert aussi bien aux **libellés de colonne** qu'aux **cellules** (cf.
    `_clean_cell`) : RaceResult emploie le même encodage des deux côtés. C'est
    ce second usage qui impose la sévérité de la reconnaissance — un libellé de
    colonne est écrit par l'outil, une cellule est saisie par un organisateur.
    Trois refus explicites, chacun contre une corruption constatée :

    1. **Toutes** les parties doivent être des variantes bien formées. Une seule
       qui ne l'est pas désarme la reconnaissance et rend la valeur intacte : la
       forme `{…|…}` où une partie est du texte libre n'est pas un enrobage
       i18n, et en extraire une variante reviendrait à jeter le reste.
    2. La clé doit avoir la forme d'un code de langue — **exactement deux
       lettres**, comme les 266 clés relevées sur le panel et comme ISO 639-1 —
       sans quoi `"{Team: Bleu}"` perd son `Team` et `"{Cat:S4M}"` son `Cat`.
    3. Si **toutes** les variantes sont vides (`"{FR:}"`), la valeur est rendue
       intacte plutôt que réduite à `""` : vider une cellule en silence est le
       plus coûteux des résultats, puisque rien en aval ne peut le rattraper.
    """
    trouve = _RE_LABEL_I18N.match(label)
    if not trouve:
        return label

    variantes: dict[str, str] = {}
    for partie in trouve.group(1).split("|"):
        forme = _RE_VARIANTE_I18N.match(partie)
        if not forme:
            return label
        variantes[forme.group(1).upper()] = forme.group(2)

    for cle in ("FR", "EN"):
        if variantes.get(cle):
            return variantes[cle]
    return next((v for v in variantes.values() if v), label)


def _clean_cell(brut) -> str:
    """Cellule débarrassée de ses décorations d'affichage.

    L'enrobage i18n `{EN:…|FR:…}` ne décore pas que les libellés de colonne : il
    voyage aussi dans les **valeurs**. Mesuré sur l'event 401699, dont les 33
    cellules de catégorie relais entraient en base telles quelles
    (`category = '{EN:Men|FR:Masculin}'`) — illisible en UI et non regroupable.
    `_label_i18n` est donc appliqué ici, sur le chemin de toutes les cellules,
    plutôt que dupliqué rôle par rôle.

    C'est un chemin exigeant : une cellule est du **texte libre** saisi par un
    organisateur, là où un libellé de colonne est écrit par l'outil. La
    reconnaissance de l'enrobage est donc volontairement sévère — enrobage
    complet, sans accolade interne, dont *toutes* les parties sont des variantes
    à clé de langue et dont au moins une est non vide (cf. `_label_i18n`, qui
    détaille les trois refus et la corruption que chacun évite).

    Mesuré sur les 176 691 cellules des 17 épreuves capturées : 33 cellules
    transformées (toutes sur 401699, toutes de la forme i18n attendue), et une
    seule autre cellule contenant `{`, `}` ou `|` — `'ROBERT Julie}'`, une
    accolade parasite dans un nom — laissée intacte. Le resserrement de la
    reconnaissance ne déplace aucune de ces 33 cellules ni aucun libellé du
    panel : il ne protège que des formes non observées, ce qui est précisément
    son objet.
    """
    if brut is None:
        return ""
    return _label_i18n(_RE_IMG.sub("", str(brut)).strip().lstrip("#").strip())


# `"1.S4M"` — le rang colle le libellé, forme `#[Classement.p][AGEGROUP…]`.
_RE_RANG_PREFIXE = re.compile(r"^(\d+)\.\s*(.*)$")
# `"M0M (1.)"` — le rang suit entre parenthèses, forme `X & iif(…)`. Le point
# final est facultatif ici : `sexe`/`categorie` sont des vocabulaires fermés
# (`"M"`, `"S4M"`) où un suffixe `(44)` sans point ne peut pas survenir.
_RE_RANG_SUFFIXE = re.compile(r"^(.*?)\s*\(\s*(\d+)\.?\s*\)$")
# Même forme, mais point final EXIGÉ : `nom`/`club`/`temps` sont du texte
# libre saisi par les organisateurs, où une parenthèse finale sans point est
# un contenu légitime (code départemental `"TRIATHLON CLUB NANTAIS (44)"`,
# numéro d'équipe de relais `"TCN (1)"`) et non un rang collé. Seul le point,
# marqueur de rang effectif de RaceResult (présent dans toutes les captures
# réelles : `(1.)`, `(10.)`, `(5.)`), distingue les deux sans ambiguïté.
_RE_RANG_SUFFIXE_STRICT = re.compile(r"^(.*?)\s*\(\s*(\d+)\.\s*\)$")


def _split_rank_category(cell: str) -> tuple[int | None, str]:
    """Sépare une cellule « libellé + rang » en (rang, libellé).

    Deux formes coexistent selon la façon dont l'épreuve compose sa colonne :
    `#[ClassementCatégorie.p][AGEGROUP.NAMESHORT]` produit `"1.S4M"`, tandis que
    `[AGEGROUP1.NAMESHORT] & iif(…;" (" & [RANK3p] & ")")` produit `"M0M (1.)"`.
    Une cellule sans rang est un libellé nu (cas des non-finishers).
    """
    cell = _clean_cell(cell)
    trouve = _RE_RANG_PREFIXE.match(cell)
    if trouve:
        return int(trouve.group(1)), trouve.group(2).strip()
    trouve = _RE_RANG_SUFFIXE.match(cell)
    if trouve:
        return int(trouve.group(2)), trouve.group(1).strip()
    return None, cell


def _strip_rank_suffix(valeur: str) -> str:
    """Décolle un rang suffixé (`"2:08:00 (1.)"` → `"2:08:00"`) d'une cellule.

    Toute colonne issue d'une concaténation `[X] & " (" & [X.OVERALL.P] & ")"`
    porte son rang collé de cette façon — un segment de course, mais aussi
    bien `nom`, `club` ou `temps` : le point fixe de `_peel` (C2) fait
    désormais converger vers ces rôles des expressions composées qui
    restaient opaques avant, sans garantie que leur valeur soit épargnée par
    le même motif de concaténation que les segments. Pour un segment,
    `_RE_DUREE` rejette la cellule polluée et le split est perdu ; pour
    `total_time`, `normalize_time` est permissif et laisserait passer
    `"3:18:21 (5.)"` tel quel — d'où ce décollage systématique plutôt qu'un
    relâchement de `normalize_time` ou de `_RE_DUREE`, tous deux proscrits.

    Utilise `_RE_RANG_SUFFIXE_STRICT` (point final exigé), pas
    `_RE_RANG_SUFFIXE` : `nom` et `club` sont du texte libre où une parenthèse
    finale sans point est un contenu légitime (code départemental, numéro
    d'équipe de relais), à la différence de `sexe`/`categorie` (vocabulaire
    fermé, traités par `_split_rank_category`) où l'ambiguïté n'existe pas.
    """
    trouve = _RE_RANG_SUFFIXE_STRICT.match(valeur)
    return trouve.group(1).strip() if trouve else valeur


# Vocabulaire temps franco-anglais (C4) : un préfixe d'arrivée
# (`temps`/`arrivee`/`finish`) suivi d'un suffixe qui distingue chip/gun/texte.
# Une table d'égalités exactes échoue en silence hors relevé : les 9 épreuves
# du panel n'exposaient que les variantes françaises et `Finish` nu, et
# l'épreuve 380823 (Bike & Run de Pontcharra), qui ne publie que `Finish.GUN`,
# y perdait ses 58 temps (`raw_data` contenait pourtant `'Finish.GUN':
# '31:27'`). La règle de forme généralise sans élargir à l'aveugle : préfixe et
# suffixe restent deux alternations **fermées**, ancrées `^…$` — `finisher.chip`
# et `tempsintermediaire.gun` ne passent pas. `temps` nu reste géré à part,
# dans la table d'égalités exactes de `_role`.
#
# Priorité entre les trois suffixes (cf. `_role` puis le repli de
# `_map_columns`) : **chip > gun > texte**. Chip et gun sont deux temps
# officiels réellement observés (`Arrivée.*`, 411749/410891) ; `.text` ne l'a
# jamais été sous ces trois racines. Le rôle distinct `temps_texte` existe pour
# qu'un `.TEXT` énuméré **avant** un `.CHIP` dans `Fields` ne squatte pas la
# place du chip (`_map_columns` retient le premier champ qui revendique un rôle).
_RE_TEMPS_SUFFIXE = re.compile(r"^(temps|arrivee|finish)\.(gun|chip|text)$")

# `FinishResult.TEXT` (C1) — racine distincte, appariée à son **seul** suffixe.
#
# Mesuré sur 406211 (World Triathlon Para Cup, Besançon) : ses 13 listes
# publiées exposent leur chrono sous
# `switch([{Selector.Splits}.NAME]=[Finish.NAME];[FinishResult.TEXT];…)`, que
# `_peel` réduit à `finishresult.text`. Sans cette entrée, ses 42 participants
# sortent sans `total_time` alors que la valeur est dans la ligne, et
# `services/cache.is_fresh` classe la course « en cours » (TTL 10 min au lieu
# de 30 j) — d'où un re-scraping perpétuel.
#
# Constante à part, et non quatrième racine de l'alternation ci-dessus, dont le
# suffixe est mutualisé : `finishresult.gun`/`.chip` y deviendraient reconnus,
# donc de priorité **haute**, alors qu'aucun n'a jamais été observé. L'appariement
# rend vraie **par construction** la propriété qui fait la sûreté de C1 —
# `finishresult` ne peut obtenir que `temps_texte`, le rôle le plus faible. Une
# épreuve qui publierait un jour `FinishResult.GUN` verrait sa valeur partir en
# `raw_data` : visible et récupérable, plutôt que promue en silence.
_RE_TEMPS_RESULTAT_TEXTE = re.compile(r"^finishresult\.text$")


def _role(peeled: str) -> str:
    """Rôle sémantique d'une expression pelée, "" si non reconnu.

    Vocabulaire relevé sur les 9 épreuves du panel (§6 du sondage) : le jeu
    initial, calibré sur une seule épreuve, laissait 506 lignes sur 507 sans nom
    ni temps sur une autre.

    Ordre des tests significatif. Les rangs nommés passent **avant** la règle du
    suffixe `.p`, car `OuStatut([AUTORANK.p])` est le rang général et non un rang
    de split : traité par la règle générique, il était écarté et l'épreuve
    perdait son classement. La règle du suffixe reste indispensable pour tout le
    reste — une expression suffixée `.p` / `.overall.p` est **toujours** un rang,
    jamais un temps, sans quoi `[Natation.OVERALL.P]` (« 2. ») passerait pour le
    temps de natation, qui vit dans la colonne suivante. La casse du suffixe
    varie (`.P` et `.p` coexistent) : le pelage ayant tout mis en minuscules, la
    comparaison est de fait insensible à la casse.
    """
    # Le dossard vient de `DataFields.index("BIB")`, jamais d'une colonne
    # d'affichage : sans cette écartement explicite, `"#"&[BIB]` (étiqueté
    # « N° ») se faisait passer pour un segment de course.
    if peeled in ("bib", "displaybib", "dossard", "dossardbis"):
        return "dossard_affiche"  # colonne à écarter
    if "classementgeneral" in peeled or "autorank" in peeled:
        return "rang"
    if "classementcategorie" in peeled or "agegroup" in peeled:
        return "rang_categorie"
    if "categorie" in peeled or "category" in peeled:
        return "categorie"
    # `#[ClassementMF.p][SexeMF]` colle le rang de sexe au sexe : reconnu ici,
    # avant la règle du suffixe, car la cellule porte les deux.
    if "sexemf" in peeled:
        return "sexe"
    if peeled.endswith(".p"):
        return "rang_de_split"  # colonne à écarter
    if any(
        motif in peeled
        for motif in ("affichernom", "nomrelais", "nomequipe", "lfname", "displayname")
    ):
        return "nom"
    if "club" in peeled:
        return "club"
    if peeled in ("sex", "sexe", "gender"):
        return "sexe"
    if peeled in (
        "time", "temps", "tempstotal", "tempsfinal", "tempsfinal.decimal",
        "tempscorrige", "tempsoustatut", "finish", "arrivee",
    ):
        return "temps"
    # Priorité chip > gun > texte : cf. le commentaire de `_RE_TEMPS_SUFFIXE`.
    # `_map_columns` résout le repli pistolet, `_build_result` le repli texte.
    trouve = _RE_TEMPS_SUFFIXE.match(peeled)
    if trouve:
        suffixe = trouve.group(2)
        if suffixe == "gun":
            return "temps_pistolet"
        if suffixe == "text":
            return "temps_texte"
        return "temps"
    if _RE_TEMPS_RESULTAT_TEXTE.match(peeled):
        return "temps_texte"
    return ""


# Colonnes d'agrément (drapeau, photo, écart au leader) que le §6 du sondage
# demande d'exclure **explicitement** de la candidature au rôle de segment.
#
# L'exclusion porte sur l'**expression de colonne** pelée, jamais sur le libellé
# affiché : sur l'event 406211, `CustomFlag` est étiqueté `{FR:Nat.|EN:Team}`,
# soit « Nat. » une fois l'i18n retiré (I1) — indiscernable de « Natation ».
# Seule l'expression distingue les deux sans ambiguïté.
#
# Ce que la mesure établit, entrée par entrée, sur les 17 épreuves capturées :
#
#   - `customflag` (27 listes) est **la seule qui porte réellement** : elle pèle
#     en un token simple, est étiquetée sur 3 épreuves, et entrait donc bien
#     dans `segments`. Ses 766 cellules n'étaient neutralisées que parce que
#     leur valeur `[img:…]` est effacée par `_clean_cell` et devient falsy —
#     par accident, pas par conception. Une épreuve qui servirait son drapeau
#     autrement (code pays en texte) rouvrirait le faux positif.
#   - `lienphotos` pèle aussi en token simple (13 listes, 3 graphies), mais
#     n'apparaît que dans `DataFields`, jamais dans `list.Fields` : elle n'est
#     aujourd'hui candidate à rien. Entrée **défensive**.
#   - `nation.iocname`, `icone("photos")` et `gaptimetop(…)` sont déjà écartées
#     par la forme (`_RE_TOKEN_SIMPLE` refuse le point et la parenthèse).
#     Entrées **défensives** elles aussi : elles nomment l'intention plutôt que
#     de dépendre d'une propriété de `_RE_TOKEN_SIMPLE` qui pourrait bouger.
#
# Deux colonnes de même nature observées hors de cette liste —
# `ChampionOrTeamJersey` et `TeamJersey`, des maillots en `[img:…]` sur 392745 —
# restent candidates et neutralisées par leur seule valeur. Elles ne figurent
# pas au §6 ; les ajouter ici serait un élargissement non instruit.
_EXCLUSIONS_EXACTES = frozenset({"customflag", "lienphotos", "nation.iocname"})
_EXCLUSIONS_PREFIXES = ("icone(", "gaptimetop(")


def _colonne_exclue(peeled: str) -> bool:
    """Vrai si l'expression pelée désigne une colonne d'agrément, jamais un segment.

    **Portée exacte** : cette garde n'est consultée que sur la branche « segment
    candidat » de `_map_columns`. Elle n'écarte donc pas une colonne qui
    obtiendrait d'abord un **rôle** via `_role` — celui-ci est testé avant. La
    distinction est inerte aujourd'hui (aucune des cinq entrées ne matche
    `_role`) mais elle n'est pas garantie par construction : ce n'est pas une
    exclusion générale de la colonne, seulement de sa candidature au rôle de
    segment.

    Angle mort consigné : la comparaison des enrobages est faite sur la
    parenthèse **collée** au nom. `Icone ("photos")`, avec une espace, ne serait
    pas exclu. Variante jamais observée sur le panel (13 listes, toutes en
    `Icone("photos")`), et `_peel` ne normalise pas les espaces — à traiter si
    une épreuve la produit un jour, plutôt qu'à deviner ici.
    """
    return peeled in _EXCLUSIONS_EXACTES or peeled.startswith(_EXCLUSIONS_PREFIXES)


def _map_columns(
    payload: dict,
) -> tuple[dict[str, int], list[tuple[str, int]], dict[str, int]]:
    """(rôles, segments, extras) — l'index de chaque colonne du payload.

    Étage 1, l'index : `col = DataFields.index(Field.Expression)`, l'algorithme
    exact de `RRPublish.js`. `DataFields` est à la **racine du payload**
    (`payload["list"]["DataFields"]` vaut `null`) et préfixe toujours `BIB` et
    `ID`, qui n'ont pas d'entrée dans `Fields`. Cette indirection reste
    indispensable : `DataFields` compte régulièrement plus d'entrées que
    `Fields` (20 contre 18 sur Rumilly, 22 contre 19 sur Genève), donc lire les
    colonnes positionnellement les décalerait toutes. Le dossard, lui, vient de
    `DataFields.index("BIB")` et ne passe par aucune heuristique.

    Étage 2, le rôle : cf. `_role`. Un champ dont l'expression est un token nu
    entre crochets (`[Natation]`) et sans suffixe de rang est un **segment**,
    étiqueté par son `Label` (passé par `_label_i18n`), sauf si son expression
    figure dans la liste d'exclusion des colonnes d'agrément
    (cf. `_colonne_exclue`). Tout le reste part en extras → `raw_data`.

    `Fields` vit sous `payload["list"]`.
    """
    data_fields = [str(e) for e in payload.get("DataFields") or []]
    index_par_expr = {expr: i for i, expr in enumerate(data_fields)}

    roles: dict[str, int] = {}
    segments: list[tuple[str, int]] = []
    extras: dict[str, int] = {}

    if "BIB" in index_par_expr:
        roles["bib"] = index_par_expr["BIB"]

    champs_liste = (payload.get("list") or {}).get("Fields")
    for champ in champs_liste or []:
        expr = str(champ.get("Expression") or "")
        col = index_par_expr.get(expr)
        if col is None:
            logger.debug("RaceResult : champ sans colonne de données (%r)", expr)
            continue
        peeled = _peel(expr)
        role = _role(peeled)
        if role in ("rang_de_split", "dossard_affiche"):
            continue
        if role and role not in roles:
            roles[role] = col
            continue
        label = _label_i18n(str(champ.get("Label") or "").strip())
        # Segment candidat : expression réduite à un token simple, étiquetée.
        # Les crochets ne sont PAS exigés — certaines épreuves écrivent
        # `Natation` là où d'autres écrivent `[Natation]`, et l'exigence les
        # privait de tous leurs splits. La qualification finale se fait sur la
        # forme des valeurs, ligne à ligne (cf. `_RE_DUREE`).
        if (
            not role
            and label
            and not _colonne_exclue(peeled)
            and _RE_TOKEN_SIMPLE.match(peeled)
        ):
            segments.append((label, col))
        else:
            # Un rôle déjà pris ne doit pas faire disparaître la colonne : elle
            # part en extras plutôt que d'être perdue silencieusement. Cas réel :
            # une liste relais expose `ucase([NomRelais])` (nom d'équipe) puis
            # `AfficherNoms` (les équipiers) — les deux pèlent vers « nom ».
            extras[expr] = col

    # La catégorie partage la colonne du rang de catégorie (cellule « 1.S4M »),
    # sauf si une colonne de catégorie distincte a déjà été reconnue.
    if "rang_categorie" in roles:
        roles.setdefault("categorie", roles["rang_categorie"])
    # Temps au pistolet en repli quand l'épreuve n'expose pas de temps réel.
    # Le gun est un champ d'horloge : sa valeur est une durée ou rien, il peut
    # donc être promu ici, sans regarder les lignes.
    if "temps_pistolet" in roles:
        roles.setdefault("temps", roles.pop("temps_pistolet"))
        roles.pop("temps_pistolet", None)
    # `temps_texte` n'est **pas** promu ici, à la différence du pistolet : une
    # colonne `.text` porte le *texte affiché*, qui vaut le chrono sur une
    # ligne terminée mais un libellé de statut (`"DNF"`, `"DSQ"`) sur les
    # autres. La promotion est donc ligne à ligne, sous condition de durée,
    # dans `_build_result` — cf. le commentaire de `total_time` qui s'y trouve.
    return roles, segments, extras


_RE_PREFIXE_GROUPE = re.compile(r"^#\d+_")


def _strip_group_prefix(cle: str) -> str:
    """Retire le préfixe d'ordonnancement d'une clé de groupe (`#1_Distance M`).

    Le numéro n'est qu'un rang d'affichage : il ne code ni le contest ni le
    statut. `#2_Abandons` et `#3_Non Partants` sur une épreuve, `#2_Non Partants`
    sur une autre — s'y fier ferait passer des non-partants pour des abandons.
    """
    return _RE_PREFIXE_GROUPE.sub("", str(cle)).strip()


def _iter_groups(
    data,
    *,
    contest: str = "",
    statut: str = "",
    profondeur: int = 0,
    contests_connus: frozenset[str] = frozenset(),
) -> list[tuple[str, str, list]]:
    """[(libellé contest, libellé statut, lignes), …] depuis l'arbre `data`.

    La profondeur de `data` **varie** — tableau plat, un niveau, ou deux — et
    parfois au sein d'une même épreuve. On descend donc récursivement jusqu'aux
    feuilles au lieu de présumer une forme fixe.

    Le niveau 0 nomme le **contest** (`#1_Distance M`, qui recoupe exactement
    `config["contests"]`) — **sauf** s'il est en réalité un statut. Un groupe de
    niveau 0 `#2_Abandons` produisait `contest="Abandons", statut=""`, perdant le
    statut des abandons (issue #64). Un libellé de niveau 0 n'est donc reclassé
    en statut que s'il est reconnu par la table **fermée** de
    `derive_status_from_label` **et** absent de `contests_connus` : ce croisement
    lève le risque symétrique — un contest légitimement nommé d'après un jeton de
    statut figure dans `contests`, il reste un contest.

    Les niveaux suivants nomment le statut — mais pas toujours : sur l'event
    406212 ils portent `#1_Masculin` / `#1_Féminin`, un groupement par **sexe**.
    Le libellé n'est donc retenu comme statut que s'il est reconnu par la même
    table ; tout libellé inconnu est un groupement neutre qui laisse le statut
    hérité intact. Traiter l'inconnu comme un abandon marquerait DNF les 175
    finishers de ce contest.
    """
    if isinstance(data, list):
        return [(contest, statut, data)] if data else []
    if not isinstance(data, dict):
        if data is not None:
            logger.warning(
                "RaceResult : nœud de données ignoré, ni dict ni liste (%r)", type(data)
            )
        return []

    groupes: list[tuple[str, str, list]] = []
    for cle, contenu in data.items():
        libelle = _strip_group_prefix(cle)
        statut_reconnu = derive_status_from_label(libelle)
        if profondeur == 0:
            # À la racine, un libellé reconnu comme statut et absent des contests
            # est un groupe de statut (`Abandons`), pas un contest : il porte le
            # statut et laisse le contest hérité (vide) intact.
            if statut_reconnu and libelle.strip().lower() not in contests_connus:
                # On propage le libellé **brut** (comme à la profondeur ≥ 1) :
                # `_build_result` re-dérive la constante STATUS_* en aval.
                groupes += _iter_groups(
                    contenu, contest=contest, statut=libelle,
                    profondeur=1, contests_connus=contests_connus,
                )
            else:
                groupes += _iter_groups(
                    contenu, contest=libelle, statut=statut,
                    profondeur=1, contests_connus=contests_connus,
                )
        else:
            reconnu = libelle if statut_reconnu else statut
            groupes += _iter_groups(
                contenu, contest=contest, statut=reconnu,
                profondeur=profondeur + 1, contests_connus=contests_connus,
            )
    return groupes


_NON_FINISHERS = (STATUS_DNF, STATUS_DNS, STATUS_DSQ)


# ── Noms d'équipe : ne pas les découper en (nom, prénom) (issue #63) ─────────
#
# `split_athlete_name` (partagé, `scrapers/utils.py`) est calibré pour un nom de
# personne. Sur un nom d'équipe (« GUILLAUME & ANTHONY », « Les Inconnus
# Associés »), il mutile l'identité. On ne le corrige pas là — d'autres scrapers
# en dépendent, et des noms de personne portent `/` ou `-` — mais on garde son
# appel dans `_build_result`, à partir de deux signaux propres à RaceResult.
_CHAMPS_NOM_EQUIPE = ("nomrelais", "nomequipe", "affichernoms")


def _est_nom_equipe(nom_col_expr: str, valeur: str) -> bool:
    """Vrai si la cellule « nom » porte un nom d'équipe, à ne pas découper.

    Deux gardes :

    1. **Par valeur** : `&` sépare deux personnes (« GUILLAUME & ANTHONY »). Il
       n'apparaît jamais dans un nom de personne, contrairement à `/` ou `-`
       (que `split_athlete_name` doit continuer de couper) : garde sûre, valable
       même sur une colonne mixte. La virgule est écartée — `LFNAME` rend
       « NOM, Prénom » pour un individu.
    2. **Par colonne** : `NomRelais` / `NomEquipe` / `AfficherNoms` (pluriel :
       les équipiers) sert une colonne **entièrement** d'équipe. La
       conditionnelle `if([Relais]=1;[NomRelais];[AfficherNom])` en est exclue :
       elle mêle équipes et individus ligne à ligne, et `_peel` la réduit à
       `nomrelais` — traiter alors toute la colonne en équipe cesserait de
       découper ses individus. Ses lignes d'équipe retombent sur la garde 1.
    """
    if "&" in valeur:
        return True
    if ";" in nom_col_expr or _RE_COMPARAISON.search(nom_col_expr):
        return False
    return _peel(nom_col_expr) in _CHAMPS_NOM_EQUIPE


def _colonne_nom_conditionnelle_equipe(nom_col_expr: str) -> bool:
    """Colonne « nom » conditionnelle capable de rendre une équipe (angle mort #63).

    Une conditionnelle `if([Relais]=1;ucase([NomRelais]);[AfficherNom])` mêle
    équipes et individus : un nom d'équipe **sans `&`** y échappe aux deux gardes
    de `_est_nom_equipe`. On ne peut pas le détecter ligne à ligne (le champ
    `[Relais]` par ligne n'est pas exposé de façon fiable), mais on repère la
    colonne — conditionnelle **et** pelant vers un champ d'équipe — pour la
    signaler. `if([STATUS]<>2;[AfficherNom])` pèle vers `affichernom` → False.
    """
    if ";" not in nom_col_expr and not _RE_COMPARAISON.search(nom_col_expr):
        return False
    return _peel(nom_col_expr) in _CHAMPS_NOM_EQUIPE


def _nom_expression(payload: dict, roles: dict[str, int]) -> str:
    """Expression source de la colonne ayant gagné le rôle « nom » (issue #63).

    `_map_columns` ne retient que l'index de colonne ; on re-dérive l'expression
    depuis `DataFields` pour que les gardes ci-dessus puissent juger la colonne.
    `""` si l'épreuve n'expose pas de colonne « nom ».
    """
    col = roles.get("nom")
    if col is None:
        return ""
    data_fields = [str(e) for e in payload.get("DataFields") or []]
    return data_fields[col] if col < len(data_fields) else ""


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
    nom_col_expr: str = "",
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

    # `nom`/`club`/`temps` peuvent désormais provenir d'une expression composée
    # que C2 a fait converger vers ce rôle (`[TIME] & " (" & [TIME.OVERALL.P] &
    # ")"`, imbriquée ou non dans un `if(…)`) : leur valeur porte alors le même
    # rang collé qu'un segment, et `_strip_rank_suffix` les protège pareil —
    # avec la variante stricte de la regex (point exigé), car ce sont des
    # champs de texte libre où une parenthèse finale peut être légitime.
    # `sexe`/`categorie` passent par `_split_rank_category`, qui fait de même
    # avec la regex permissive (vocabulaire fermé, pas d'ambiguïté possible).
    # Nom d'équipe (issue #63) : `split_athlete_name` le mutilerait
    # (« GUILLAUME & ANTHONY » → nom='GUILLAUME', prenom='& ANTHONY'). On garde
    # alors la cellule entière comme `nom`, `prenom` vide. Cf. `_est_nom_equipe`.
    nom_cell = _strip_rank_suffix(cellule("nom"))
    if _est_nom_equipe(nom_col_expr, nom_cell):
        nom, prenom = nom_cell, ""
    else:
        nom, prenom = split_athlete_name(nom_cell)
    r.athlete_name, r.athlete_firstname = nom, prenom
    r.club = _strip_rank_suffix(cellule("club"))
    # `ucase([SEX]) & iif(…)` sérialise « M (1.) » : le rang de sexe voyage dans
    # la même cellule que le sexe et doit en être détaché.
    r.rank_gender, r.gender = _split_rank_category(cellule("sexe"))
    r.rank_category, r.category = _split_rank_category(cellule("categorie"))
    # `total_time` n'a aucun garde-fou de forme en aval : `normalize_time`
    # renvoie son entrée **telle quelle** quand elle ne la reconnaît pas, si
    # bien qu'un libellé partirait en base comme chrono.
    #
    # La colonne du rôle `temps` est **gardée par la reconnaissance de
    # `normalize_time`**, non par `_RE_DUREE` : ce dernier est plus étroit (il
    # rejette `1h23'45`, que `normalize_time` sait lire), donc l'employer ici
    # perdrait des formats légitimes rendus par une horloge `.chip`/`.gun`. Le
    # rôle `temps` est en effet plus large que ces horloges : la table
    # d'égalités exactes de `_role` y range `tempsoustatut`, et `OuStatut(…)`
    # étant un enrobage pelé, `OuStatut([Temps])` obtient ce rôle et peut donc
    # rendre un statut. Sans cette garde, un libellé (`"DNF"`, `"Abandon"`)
    # partait en `total_time` comme un chrono, puis la ligne était marquée
    # `finisher` par la clôture ci-dessous (trou pré-existant à C1, mesuré
    # latent — aucune valeur non-durée sur les 12 épreuves du panel ; issue #62).
    #
    # La colonne `.text`, elle, rend le *texte affiché* : le chrono sur une
    # ligne terminée, mais `"DNF"`/`"DSQ"` sur un non-finisher. Elle n'est donc
    # retenue en repli que si sa valeur **est** une durée — même qualification
    # `_RE_DUREE` que les segments plus bas, et pour la même raison : un
    # segment non reconnu et un temps d'arrivée non reconnu sont le même
    # signal. Sans cette garde, un `"DNF"` deviendrait un `total_time` et la
    # ligne serait ensuite marquée `finisher` par la clôture ci-dessous.
    #
    # Ce repli étant évalué **ligne à ligne**, il couvre trois cas et non un
    # seul : l'épreuve qui ne publie aucun chip ni gun (406211), la ligne où une
    # colonne d'horloge existe et rend une cellule vide — que la résolution en
    # amont, dans `_map_columns`, abandonnait définitivement au profit d'une
    # colonne muette — et, depuis #62, la ligne dont la colonne `temps` rend un
    # statut plutôt qu'une durée. Le repli restant borné par `_RE_DUREE`, il ne
    # peut injecter qu'une vraie durée, jamais un statut. Élargissement latéral
    # assumé, et inerte sur le panel : aucune épreuve n'y gagne ni n'y perd de temps.
    temps = _strip_rank_suffix(cellule("temps"))
    if not _RE_DUREE_NORMALISEE.match(normalize_time(temps)):
        temps = ""
    if not temps:
        candidat = _strip_rank_suffix(cellule("temps_texte"))
        if _RE_DUREE.match(candidat):
            temps = candidat
    r.total_time = normalize_time(temps)
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

    # Une colonne candidate ne devient un segment que si sa valeur est bien une
    # durée : c'est ce qui écarte les colonnes « Tours » ou « Distance », dont
    # l'expression est un token simple indiscernable de celle d'un split. Le
    # rang suffixé (`"33:18 (10.)"`) est décollé AVANT cette qualification :
    # `_RE_DUREE` le rejetterait tel quel et ferait perdre le split entier.
    r.segments = [
        (label, normalize_time(valeur))
        for label, col in segments
        if col < len(ligne)
        and (cellule_brute := _clean_cell(ligne[col]))
        and (valeur := _strip_rank_suffix(cellule_brute))
        and _RE_DUREE.match(valeur)
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


def _fetch_list(
    event_id: str,
    key: str,
    listname: str,
    contest: str,
    client: httpx.Client,
) -> dict | None:
    """Payload d'une liste pour un contest donné, `None` si indisponible.

    Un 404 (liste annoncée mais non servie) est journalisé en `debug` et renvoie
    `None` — le balayage continue. Les autres erreurs HTTP remontent : une
    épreuve à moitié importée dont toutes les lignes portent un temps bascule en
    « terminée » pour `services/cache.is_fresh`, ce qui gèle le cache 30 jours
    sur une perte évitable, alors qu'un échec dur remonte en `BatchFailure` et
    sera re-tenté. Si de la robustesse est voulue ici, la réponse est un retry
    avec backoff, pas une dégradation silencieuse.
    """
    resp = client.get(
        f"{_API_BASE}/{event_id}/results/list",
        params={
            "key": key,
            "listname": listname,
            "contest": contest,
            "page": "results",
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
    """Nombre de champs **renseignés** — arbitre les doublons entre listes.

    Compte les données, pas les colonnes : une liste large mais vide ne doit pas
    l'emporter sur une liste étroite et renseignée, sous peine d'effacer le club,
    qui est le critère d'attribution au club (TCN).
    """
    champs = (
        r.athlete_name, r.athlete_firstname, r.club, r.category, r.gender, r.total_time
    )
    return (
        sum(1 for c in champs if c)
        + len(r.segments or [])
        + sum(1 for v in r.raw_data.values() if v)
    )


def _contests_normalises(contests: dict) -> frozenset[str]:
    """Valeurs de `contests` normalisées (`strip().lower()`) pour comparaison.

    Une seule normalisation partagée entre le croisement de niveau 0 de
    `_iter_groups` (issue #64) et `_groupes_zero_fiables`, qui comparent tous
    deux un libellé de groupe aux contests déclarés.
    """
    return frozenset(
        str(v).strip().lower() for v in (contests or {}).values() if str(v).strip()
    )


def _groupes_zero_fiables(labels: set[str], contests: dict) -> bool:
    """Les libellés de groupe des listes `Contest="0"` recoupent-ils `contests` ?

    `Contest="0"` signifie « toutes catégories » : la liste ne dit pas à quel
    contest ses lignes appartiennent, et le libellé de groupe de niveau 0 est le
    seul indice disponible. Mais ce libellé n'est **pas** toujours un contest —
    mesuré, pas supposé :

    - 380823 (Bike & Run de Pontcharra) : une seule liste, groupes `10 Km` /
      `20 Km`, tous deux présents dans `contests`, dossards **disjoints**. Le
      groupement mirroite fidèlement les contests : s'en priver fusionnerait deux
      courses de distances différentes en une.
    - 409130 (24H Rollers du Mans) : trois listes, groupes `24h DECOUVERTE`
      (une **catégorie** — la liste s'appelle « Classement par catégories »),
      `14H`, et un groupe vide. Les dossards se **recouvrent massivement** : les
      72 de `24h DECOUVERTE` sont tous dans les 456 de `14H`, et 297 des 370 de
      la liste Qualifs aussi. Qualifier par ces libellés fabrique 3 `Course` et
      302 dossards présents dans plusieurs d'entre elles.

    D'où le critère **tout ou rien à l'échelle de l'épreuve** : on ne fait
    confiance au groupement de niveau 0 que si **chacun** de ses libellés est une
    valeur de `contests`. Un seul libellé étranger (catégorie, sélecteur de
    split, statut) suffit à disqualifier le groupement entier, car il révèle un
    axe d'affichage et non la partition en contests. Les lignes retombent alors
    sur le nom d'épreuve nu : une seule `Course`, où la fusion par dossard
    dédoublonne au lieu de dupliquer.

    Noter que sur 409130 `14H` est bien une valeur de `contests` : une
    corroboration **par libellé** ne suffisait pas, elle laissait les 72 dossards
    de la catégorie dans une `Course` distincte de `14H` tout en les y laissant
    aussi. C'est le caractère global du critère qui ferme le défaut.
    """
    if not labels:
        return False
    connus = _contests_normalises(contests)
    return bool(connus) and all(lab.strip().lower() in connus for lab in labels)


def _prefer(nouveau: ScrapedResult, ancien: ScrapedResult) -> bool:
    """Vrai si `nouveau` doit remplacer `ancien` dans la fusion par clé.

    Une même épreuve expose couramment plusieurs listes sur un même contest
    (6 listes sur le contest 1 de l'event 392745, 3 en `Contest="0"` sur 409130) :
    la même personne y apparaît plusieurs fois, avec des colonnes différentes.

    Un statut non-finisher (DNF/DNS/DSQ) est un signal fort qui ne doit pas être
    écrasé par une ligne simplement plus riche mais muette sur le statut. Mais ce
    signal ne joue que face à une ligne concurrente sans **aucun temps d'arrivée
    réel** : un chrono est un signal plus fort qu'un statut annoncé. Sans cette
    seconde garde, une liste « Non Partants » figée à la veille (dossard
    réattribué, engagé finalement présent) écrasait temps, rang et club corrects.

    Au-delà des non-finishers, un temps d'arrivée réel prime aussi sur la seule
    richesse : une liste peut être plus large que le vrai classement (drapeau,
    écart au leader, colonnes non reconnues) tout en étant muette sur le temps.
    """
    if nouveau.status in _NON_FINISHERS and not ancien.total_time:
        return True
    if ancien.status in _NON_FINISHERS and not nouveau.total_time:
        return False
    if bool(nouveau.total_time) != bool(ancien.total_time):
        return bool(nouveau.total_time)
    return _richness(nouveau) > _richness(ancien)


def _identite_pliee(r: ScrapedResult) -> tuple[str, str]:
    """(nom, prénom) plié en minuscules et accents neutralisés, pour comparaison.

    Réutilise `_ACCENTS` afin qu'une divergence de seule casse ou de seul accent
    (« José » / « JOSE ») ne compte pas comme deux identités.
    """
    def plie(s: str) -> str:
        return (s or "").translate(_ACCENTS).strip().lower()

    return plie(r.athlete_name), plie(r.athlete_firstname)


def _identites_incompatibles(a: ScrapedResult, b: ScrapedResult) -> bool:
    """Vrai si `a` et `b` nomment deux athlètes **distincts**.

    Sert de garde à l'instrumentation de la collision de dossard du repli
    `Contest="0"` (issue #65, §13.19 du sondage) : sur une même clé de fusion,
    deux identités renseignées et différentes signalent que `_prefer` s'apprête
    à écraser une personne au profit d'une autre — le « signal à guetter » que le
    sondage réclame. « Renseignée » vaut dès qu'un champ (nom **ou** prénom) est
    présent : un patronyme seul (« JP ROUX » → prénom vide, cf.
    `split_athlete_name`) reste comparé, à dessein (voir la garde stricte infra).

    Rend **False** dès qu'un côté est anonyme (nom et prénom vides) : c'est le cas
    nominal d'une fusion d'enrichissement, où une liste sans patronyme complète
    une liste qui en porte un. Alerter là serait du bruit. La comparaison est
    tolérante à la casse et aux accents (cf. `_identite_pliee`).

    Au-delà de la casse et des accents, une divergence de **tokenisation** entre
    deux listes (« Jean-Pierre » vs « Jean Pierre », ordre nom/prénom permuté par
    une expression `AfficherNom` différente) déclencherait l'alerte. Non observé
    sur le panel — les deux listes partagent la même cellule « nom » et le même
    `split_athlete_name` — et sans conséquence (on ne fait que loguer), une telle
    divergence mérite d'ailleurs d'être signalée. Garde volontairement stricte.
    """
    ida, idb = _identite_pliee(a), _identite_pliee(b)
    if not any(ida) or not any(idb):
        return False
    return ida != idb


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Importe tous les participants d'une épreuve RaceResult.

    Balaie les listes publiées annoncées par la config et les **fusionne** : une
    liste « Individuel » et une liste « Relais » se complètent au lieu de
    s'écraser, et plusieurs listes couvrant un même contest convergent vers la
    même clé.

    Borne réseau : exactement `len(specs)` requêtes `list`, plus une `config` et
    une `results` — le contest étant explicite, il n'y a plus de balayage à
    l'aveugle. Mesuré : 4 requêtes `list` sur Rumilly (contre 15, dont 11 en 404,
    dans la version qui interrogeait la route héritée).
    """
    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        event_id = _resolve_event_id(url, client)
        config = _fetch_config(event_id, client)
        key = str(config.get("key") or "")
        contests = config.get("contests") or {}
        contests_connus = _contests_normalises(contests)
        nom_meta, jour, _ville = _fetch_meta(event_id, client)
        event_name = nom_meta or str(config.get("eventname") or "")

        specs = _iter_list_specs(config)
        # Clé de fusion (libellé de contest, dossard) : deux contests peuvent
        # porter le même dossard — c'est précisément le cas que la qualification
        # par contest règle (issue #21).
        fusion: dict[tuple[str, str], ScrapedResult] = {}

        # Phase 1 : tout récupérer (mêmes requêtes, même ordre qu'avant) avant de
        # décider des libellés. La fiabilité du groupement `Contest="0"` est une
        # propriété de l'épreuve entière (cf. `_groupes_zero_fiables`) : elle ne
        # peut pas être tranchée liste par liste.
        recuperees: list[tuple[str, dict, list]] = []
        labels_zero: set[str] = set()
        for listname, contest in specs:
            payload = _fetch_list(event_id, key, listname, contest, client)
            if payload is None:
                continue
            groupes = _iter_groups(
                payload.get("data"), contests_connus=contests_connus
            )
            recuperees.append((contest, payload, groupes))
            if contest == "0":
                labels_zero.update(cl for cl, _st, _lg in groupes)

        fiable_zero = _groupes_zero_fiables(labels_zero, contests)

        # Phase 2 : qualifier et fusionner.
        for contest, payload, groupes in recuperees:
            roles, segments, extras = _map_columns(payload)
            nom_col_expr = _nom_expression(payload, roles)
            if _colonne_nom_conditionnelle_equipe(nom_col_expr):
                logger.warning(
                    "RaceResult %s : colonne nom conditionnelle (%r) mêlant "
                    "équipes et individus — un nom d'équipe sans '&' peut être "
                    "découpé sans trace (angle mort #63)",
                    event_id, nom_col_expr,
                )
            for contest_label, status_label, lignes in groupes:
                # Le contest est **explicite** dans `TabConfig.Lists` (§3 du
                # sondage) : quand il est renseigné, il fait autorité et le
                # libellé de groupe n'est pas consulté. Ce libellé n'est en effet
                # pas fiable — mesuré sur 406211, où les clés de niveau 0 sont
                # `Finish` et `Run - Start`, des **sélecteurs de point de chrono**
                # qui écrasaient les 13 contests publiés en 2 `Course`.
                #
                # `Contest="0"` (« toutes catégories ») est le seul cas où le
                # contest n'est pas donné ; le groupement n'y est consulté que
                # s'il recoupe entièrement `contests`.
                #
                # On ne retombe **jamais** sur `listname` : c'est un nom interne
                # à pipe (`"03-Qualifs|Classement Qualifs"`), un séparateur
                # d'affichage et non une hiérarchie. Servant à la fois de
                # qualifiant de `Course` et de clé de fusion, il fabriquait une
                # `Course` fantôme *et* y dupliquait des participants déjà
                # importés sous leur vrai contest (issue #21 par la porte du
                # repli).
                if contest != "0":
                    libelle = str(contests.get(contest) or "") or f"Contest {contest}"
                elif fiable_zero:
                    libelle = contest_label
                else:
                    libelle = ""
                for ligne in lignes:
                    r = _build_result(
                        ligne, roles, segments, extras,
                        source_url=url,
                        event_name=event_name,
                        event_date=jour,
                        contest_label=libelle,
                        status_label=status_label,
                        nom_col_expr=nom_col_expr,
                    )
                    if not r.bib_number:
                        continue
                    cle = (libelle, r.bib_number)
                    ancien = fusion.get(cle)
                    # §13.19 (issue #65) : sur le repli `Contest="0"` non
                    # corroboré, toutes les lignes partagent le qualifiant vide.
                    # Deux personnes distinctes au même dossard s'y écrasent alors
                    # sans trace via `_prefer`. On ne change pas l'arbitrage — le
                    # sondage établit que le compromis est le bon — mais on rend
                    # la collision **bruyante** : muette sur tout le panel réel,
                    # elle ne se déclenche que sur une forme non observée.
                    if ancien is not None and _identites_incompatibles(r, ancien):
                        logger.warning(
                            "RaceResult %s : dossard %s en collision sous le "
                            "qualifiant %r — deux identités distinctes "
                            "(%s %s / %s %s), une sera écrasée sans trace "
                            "(cf. #65 §13.19)",
                            event_id, r.bib_number, libelle or "(aucun)",
                            ancien.athlete_name, ancien.athlete_firstname,
                            r.athlete_name, r.athlete_firstname,
                        )
                    if ancien is None or _prefer(r, ancien):
                        fusion[cle] = r

    if not fusion:
        essayees = ", ".join(nom for nom, _ in specs) or "aucune liste publiée"
        raise ValueError(
            f"Épreuve RaceResult {event_id} : aucune liste exploitable "
            f"(listes essayées : {essayees})."
        )
    return list(fusion.values())

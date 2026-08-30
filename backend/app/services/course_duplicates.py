"""Doublons suspects : la même épreuve entrée deux fois en base (#288).

Trois cas ont été trouvés **à l'œil**, par hasard, en regardant une fiche
coureur : Mesquer, Nozéen, Vertou. C'est cette découverte fortuite que ce module
remplace — il n'écrit rien, il **propose** des paires à un humain, qui tranche
ensuite avec la fusion (#289) ou l'arbitrage de sources (#285).

## Les deux seuils, côte à côte

Ils existent tous les deux, ils sont différents, et c'est voulu.

**Le seuil #277 — rapprochement automatique.** À l'import, deux publications
sont réunies sans intervention humaine si, et seulement si : les deux providers
sont dans `{klikego, breizhchrono}`, leurs identifiants de plateforme sont égaux
et non vides, leurs *heat slugs* sont égaux et non vides, et les deux épreuves
sont distinctes. Aucune tolérance, aucun score, aucune comparaison de nom ni de
date. Mesuré sur les 4 465 paires de la base de développement : **0 faux
positif** (`docs/superpowers/specs/2026-08-12-sources-multiples-epreuve-sondage.md`,
règle R).

**Le seuil #288 — suspicion, celui de ce module.** Délibérément plus large : il
ne demande pas l'égalité de l'identifiant *et* du heat, il accepte une
divergence de nom, et il tolère jusqu'à trois jours d'écart sur la date.

**Pourquoi deux seuils et non un.** Le prix d'une erreur n'est pas le même. Un
faux positif de #277 écrit en base sans que personne l'ait vu : deux épreuves
réellement distinctes sont fusionnées, un classement disparaît, et rien ne le
signale. Un faux positif d'ici coûte un coup d'œil — la paire s'affiche, un
humain la lit et l'ignore. Un faux **négatif**, en revanche, est symétriquement
plus grave ici : un doublon que la liste ne montre pas continue de fausser les
compteurs du club, et redevient trouvable seulement par hasard.

**Pourquoi pas *encore* plus large, alors.** Parce qu'une liste de suspicions
n'a de valeur que si on la lit. Le sondage a mesuré ce que coûtent les seuils
laxistes sur la base de développement, qui ne contient **aucun** vrai doublon :
rapprocher sur le nom normalisé seul en sort 37 paires, toutes fausses ; y
ajouter la suppression du suffixe de heat, 53. Une liste de 53 lignes fausses ne
se lit plus, et le premier vrai doublon s'y noierait. Les trois motifs ci-dessous
sortent **0** paire de cette même base.

## Les motifs, un ensemble fermé

Trois, nommés, sans configuration ni pondération : le besoin actuel est de
retrouver trois formes de doublon **observées**, pas d'offrir un moteur de
règles. Chacune est indispensable — aucune n'attrape le cas d'une autre.

Une paire ne sort **qu'une fois**, sous le premier motif qui la reconnaît, du
plus spécifique au plus lâche : ce que dit le chronométreur (URL, puis
identifiant) avant ce que suggère un libellé.
"""
import logging
import re
from collections.abc import Callable
from datetime import timedelta
from itertools import combinations
from urllib.parse import parse_qs, urlparse

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.core.text import deaccent
from app.repositories import (
    admin_action_log_repository,
    course_repository,
    ignored_course_duplicate_repository,
)

logger = logging.getLogger(__name__)

#: Les motifs et leur formulation à l'écran (#292). En français : c'est **la**
#: colonne qui rend la paire arbitrable sans aller ouvrir les deux épreuves.
REASON_LABELS: dict[str, str] = {
    "same_source_url": "Même URL de source",
    "shared_event_id": "Identifiant d'événement partagé",
    "close_names": "Noms proches à la même date",
}

#: Tolérance de date du motif « noms proches ». Trois jours, et non zéro : une
#: publication qui daterait l'épreuve de la veille ou du lendemain (fuseau du
#: chronométreur, week-end à cheval) resterait le même événement. Et non trente :
#: c'est la date qui remplace le millésime effacé du nom comme discriminant
#: d'édition, elle doit rester serrée devant les 364 jours qui séparent deux
#: éditions. Mesuré : ±1 j, ±3 j → 0 faux positif (sondage, règles R4 et R5).
DATE_TOLERANCE = timedelta(days=3)

#: Les deux plateformes dont l'URL porte un identifiant d'événement. Hors de ces
#: deux-là, le motif « identifiant partagé » ne s'applique pas : la forme
#: `{epoch_ms}-{ordinal}` est la leur, et un nombre long trouvé dans l'URL d'un
#: autre chronométreur ne désigne pas un événement.
PLATFORMS_WITH_EVENT_ID = frozenset({"klikego", "breizhchrono"})

#: L'identifiant d'événement Klikego / Breizh Chrono. Le suffixe `-{ordinal}`
#: **fait partie de l'identifiant** : `1517534975128-7` et `1517534975128-8` sont
#: deux éditions du même duathlon, tronquer au préfixe epoch les confondrait.
_EVENT_ID = re.compile(r"\d{10,}-\d+")

#: Un ordinal d'édition en tête de nom : `5e`, `6ème`, `2nde` exclue (jamais vue).
_EDITION_ORDINAL = re.compile(r"^\d+\s*(?:er|ere|eme|e)\b")

#: Un millésime dans le nom : `2025`, `2026`.
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def _heat_slug(url: str) -> str:
    """Le heat que cette URL désigne, ou `""` si elle désigne tout un événement.

    Définition reprise **telle quelle** du sondage, qui l'a mesurée : le
    paramètre `heat` s'il existe, sinon le troisième segment de la forme
    `/resultats-courses/{slug}-{id}/{heat}` de Breizh Chrono. Pas une
    heuristique de plus : élargir au « dernier segment de chemin » ferait passer
    `/epreuves/resultats/live/3232` (TimePulse, une URL pour six heats) pour une
    URL de heat, et c'est exactement ce que ce garde doit exclure.
    """
    adresse = urlparse(url)
    heat = parse_qs(adresse.query).get("heat", [""])[0]
    if heat:
        return heat.lower()
    segments = [segment for segment in adresse.path.split("/") if segment]
    if len(segments) == 3 and segments[0] == "resultats-courses":
        return segments[2].lower()
    return ""


def _event_id(url: str, provider: str) -> str:
    """L'identifiant d'événement de la plateforme, ou `""`.

    **Écart assumé avec le sondage**, qui demande de réutiliser les analyseurs
    d'URL des scrapers plutôt que d'écrire un motif de plus. Une seule recherche
    couvre les quatre formes d'adresse des deux plateformes, là où la réutilisation
    voudrait importer trois fonctions privées de `app/scrapers/` depuis un service.
    L'écart est tenable **ici** parce que rien n'est écrit : un identifiant mal lu
    fait apparaître ou manquer une ligne dans une liste de suspicions, qu'un humain
    relit. Il ne l'est **pas** pour #289, qui fusionne : là, la lettre du sondage
    s'applique.
    """
    if provider not in PLATFORMS_WITH_EVENT_ID:
        return ""
    trouve = _EVENT_ID.search(url)
    return trouve.group(0) if trouve else ""


def _comparable_name(name: str) -> str:
    """Le nom réduit à ce qui reste stable d'une publication à l'autre.

    Deux effacements, et ils ne sont pas gratuits : l'ordinal d'édition et le
    millésime sont **précisément** ce qui distingue deux éditions. On ne peut se
    le permettre que parce que la date les remplace comme discriminant (cf.
    `DATE_TOLERANCE`) — mesuré sur Vertou, dont une façade nomme
    `Triathlon de Vertou 2026 - S-Open` ce que l'autre nomme
    `Triathlon de Vertou - S-Open`.
    """
    texte = (deaccent(name) or "").lower()
    texte = _EDITION_ORDINAL.sub(" ", texte)
    texte = _YEAR.sub(" ", texte)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texte).split())


def _same_source_url(course: dict) -> tuple | None:
    """« Même URL de source » — deux lignes nées de la même page de résultats.

    Le cas Mesquer : une seule URL, deux `event_type`, donc deux épreuves en base
    (l'identité est `(name, event_date, event_type, is_relay)`) alors qu'une page
    de heat n'en publie qu'une.

    Le garde est le heat, pas le nom ni la date : partager une URL n'a rien de
    suspect en soi — TimePulse publie ses six heats sous une URL d'événement
    **et** sous le même nom, ce qui en sortait 16 paires fausses. Une URL qui
    désigne un seul heat, elle, ne peut pas porter deux épreuves distinctes.
    """
    if not course["source_url"] or not _heat_slug(course["source_url"]):
        return None
    return (course["source_url"],)


def _shared_event_id(course: dict) -> tuple | None:
    """« Identifiant d'événement partagé » — le même événement sous deux façades.

    Le cas Nozéen : l'édition 2026 a été importée deux fois, chez Klikego et chez
    Breizh Chrono, avec des noms différents et des nombres de participants
    différents (#261). L'identifiant `1517534975128-8`, lui, est le même — c'est
    le chronométreur qui le porte, pas nous.

    `event_type` et `is_relay` dans la clé, et le **host** et le **heat slug**
    dans la comparaison (cf. `_shared_event_id_guard`) : sans le host, les six
    swimruns de Dinard, qui partagent identifiant, type et caractère relais,
    sortaient en 15 paires fausses ; sans le heat slug, trois heats de relais
    distincts d'Audencia La Baule, partagés sous deux façades Breizh Chrono,
    sortaient en 2 paires fausses (#756, cas 2).
    """
    identifiant = _event_id(course["source_url"], course["provider"])
    if not identifiant:
        return None
    return (identifiant, course["event_type"], course["is_relay"])


def _close_names(course: dict) -> tuple | None:
    """« Noms proches à la même date » — le seul motif qui n'exige rien de l'URL.

    Le cas Vertou : wiclax est le seul des 14 fournisseurs dont l'URL ne porte
    aucun identifiant d'événement, et ses quatre formes d'adresse n'ont ni host
    ni chemin commun. Il ne reste que le nom et la date, et il faut donc bien un
    motif qui s'en contente — c'est aussi le seul qui rattraperait un doublon né
    d'une saisie manuelle.

    C'est le plus lâche des trois : le nom seul rapproche 37 paires fausses sur
    la base de développement. `event_type`, `is_relay` et la date le ramènent à
    0 — sauf pour les heats qui, comme Frenchkid Aquathlon, nomment leur
    catégorie par année de naissance : `_YEAR` l'efface comme un millésime, et
    deux catégories distinctes se retrouvent avec le même nom comparable. C'est
    `_heat_slugs_conflict`, dans la comparaison, qui les sépare (#756, cas 1).
    """
    if course["event_date"] is None:
        return None
    nom = _comparable_name(course["name"])
    if not nom:
        return None
    return (nom, course["event_type"], course["is_relay"])


def _facades_differ(gauche: dict, droite: dict) -> bool:
    """Les deux URLs viennent-elles de deux publications distinctes ?

    Le host, et non l'URL entière : deux lignes issues de la **même** façade sont
    une seule publication de l'événement, donc des heats — c'est la forme que
    prennent les six swimruns de Dinard chez `live.breizhchrono.com`. Deux
    publications, ce sont deux hosts, et c'est là seulement que le nom et le
    nombre de participants ont le droit de diverger.
    """
    return urlparse(gauche["source_url"]).netloc != urlparse(droite["source_url"]).netloc


def _dates_are_close(gauche: dict, droite: dict) -> bool:
    if gauche["event_date"] is None or droite["event_date"] is None:
        return False
    return abs(gauche["event_date"] - droite["event_date"]) <= DATE_TOLERANCE


def _heat_slugs_conflict(gauche: dict, droite: dict) -> bool:
    """Les deux heat slugs sont-ils non vides et différents ? (#756, cas 1)

    Le cas Frenchkid Aquathlon : deux catégories du même événement, distinguées
    par l'année de naissance dans le nom (`- 2013/2014 - Fille`, `- 2015 -
    Fille`), que `_YEAR` efface comme un millésime — `_comparable_name` les rend
    donc identiques. Le heat slug, lui, reste ce que le chronométreur distingue
    réellement : deux slugs non vides et différents signent deux catégories,
    jamais un doublon, quand bien même le nom et la date coïncident.
    """
    gauche_heat = _heat_slug(gauche["source_url"])
    droite_heat = _heat_slug(droite["source_url"])
    return bool(gauche_heat) and bool(droite_heat) and gauche_heat != droite_heat


def _shared_event_id_guard(gauche: dict, droite: dict) -> bool:
    """Deux façades distinctes, et le même heat. (#756, cas 2)

    Le host seul ne suffit pas : Audencia La Baule 2024 publie trois heats de
    relais légitimement distincts (entreprises, grand public, mixte) sous
    l'identifiant Breizh Chrono commun de l'événement, répartis sur deux
    façades — deux d'entre eux se retrouvaient appariés à tort, façade
    différente mais heat différent aussi. Le heat slug tranche : Nozéen, lui,
    porte le même heat (`duathlon-s---open`) des deux côtés.
    """
    if not _facades_differ(gauche, droite):
        return False
    return _heat_slug(gauche["source_url"]) == _heat_slug(droite["source_url"])


def _close_names_guard(gauche: dict, droite: dict) -> bool:
    """La date rapproche, et le heat slug ne les distingue pas. (#756, cas 1)"""
    if not _dates_are_close(gauche, droite):
        return False
    return not _heat_slugs_conflict(gauche, droite)


#: Les trois motifs, du plus spécifique au plus lâche : `(code, clé, garde)`.
#: L'ordre porte la priorité — une paire reconnue par deux motifs sort sous le
#: premier. Ensemble **fermé** : trois formes observées, pas un moteur de règles.
_REASONS: tuple[
    tuple[
        str,
        Callable[[dict], tuple | None],
        Callable[[dict, dict], bool] | None,
    ],
    ...,
] = (
    ("same_source_url", _same_source_url, None),
    ("shared_event_id", _shared_event_id, _shared_event_id_guard),
    ("close_names", _close_names, _close_names_guard),
)


def find_candidates(db: Session) -> list[dict]:
    """Les paires d'épreuves à faire arbitrer, chacune avec son motif.

    Regroupement par clé puis paires **à l'intérieur** de chaque groupe : la base
    compte ~95 épreuves aujourd'hui, mais comparer tout avec tout serait 4 465
    paires pour trois motifs, et le coût grandit en carré du nombre d'épreuves —
    inutile de le payer quand la clé du motif est justement ce qui doit être égal.

    Ordre stable, celui du catalogue (date décroissante, puis nom, puis id) : la
    liste est relue après chaque arbitrage, elle ne doit pas se réordonner sous
    les yeux de qui la traite.

    **Les paires écartées par `ignore_pair` (#754) n'y reviennent jamais.** Sans
    ce filtre, un faux positif vérifié une fois par un humain reviendrait à
    chaque rechargement de l'écran — c'est exactement ce que #754 corrige.
    """
    courses = [
        {
            "id": ligne.id,
            "name": ligne.name,
            "event_date": ligne.event_date,
            "event_type": ligne.event_type,
            "is_relay": ligne.is_relay,
            "provider": ligne.provider,
            "source_url": ligne.source_url,
            "total": ligne.total,
            "tcn_count": ligne.tcn_count,
        }
        for ligne in course_repository.list_identities_with_counts(db)
    ]
    rangs = {course["id"]: rang for rang, course in enumerate(courses)}
    ecartees = ignored_course_duplicate_repository.all_pairs(db)

    motif_par_paire: dict[tuple[int, int], str] = {}
    for code, cle, garde in _REASONS:
        groupes: dict[tuple, list[dict]] = {}
        for course in courses:
            if (valeur := cle(course)) is not None:
                groupes.setdefault(valeur, []).append(course)
        for groupe in groupes.values():
            for gauche, droite in combinations(groupe, 2):
                if garde is not None and not garde(gauche, droite):
                    continue
                paire = (gauche["id"], droite["id"])
                if (min(paire), max(paire)) in ecartees:
                    continue
                motif_par_paire.setdefault(paire, code)

    par_id = {course["id"]: course for course in courses}
    return [
        {
            "reason": code,
            "reason_label": REASON_LABELS[code],
            "courses": [par_id[gauche], par_id[droite]],
        }
        for (gauche, droite), code in sorted(
            motif_par_paire.items(), key=lambda paire: (rangs[paire[0][0]], rangs[paire[0][1]])
        )
    ]


def ignore_pair(db: Session, *, course_id_a: int, course_id_b: int, user_id: int) -> dict:
    """Écarte une paire suspecte : un faux positif vérifié une fois par un
    humain (#754).

    Deux épreuves inconnues sont un 404, la même épreuve des deux côtés un 400 :
    il n'y a rien à écarter d'une épreuve avec elle-même. Une paire déjà écartée
    est un 409 — la décision existe déjà, la répéter ne changerait rien de plus
    que l'horodatage et l'auteur, qu'on ne veut pas réécrire en silence.
    `uq_ignored_course_duplicate_pair` reste le garde qui compte réellement sous
    concurrence : la lecture préalable évite le 500 dans le cas courant, elle ne
    l'élimine pas — deux requêtes simultanées sur la même paire peuvent encore
    heurter la contrainte, même parti pris que `validate_season`.

    `entity_id` du journal est le plus petit des deux ids, comme
    `IgnoredCourseDuplicate.course_id_low` : c'est ce qui rend l'entrée
    retrouvable par `list_for_entity` sans dépendre de l'ordre dans lequel
    l'appelant a soumis la paire — `course_id_a`/`course_id_b` ne sont associés
    à aucun rôle, contrairement à `target`/`absorbed` de la fusion (#287).
    """
    if course_id_a == course_id_b:
        raise DomainError("Une épreuve ne peut pas être écartée avec elle-même.")
    if course_repository.get(db, course_id_a) is None:
        raise NotFoundError(f"Épreuve introuvable : {course_id_a}.")
    if course_repository.get(db, course_id_b) is None:
        raise NotFoundError(f"Épreuve introuvable : {course_id_b}.")
    if ignored_course_duplicate_repository.exists(
        db, course_id_a=course_id_a, course_id_b=course_id_b
    ):
        raise DuplicateError("Cette paire d'épreuves est déjà écartée.")

    ignoree = ignored_course_duplicate_repository.create(
        db, course_id_a=course_id_a, course_id_b=course_id_b, user_id=user_id
    )
    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="course_duplicate.ignore",
        entity_type="course_duplicate",
        entity_id=min(course_id_a, course_id_b),
        payload={"course_id_a": course_id_a, "course_id_b": course_id_b},
    )
    logger.info(
        "Admin %s ignored course duplicate pair (%s, %s)", user_id, course_id_a, course_id_b
    )
    return {
        "course_id_a": course_id_a,
        "course_id_b": course_id_b,
        "ignored_at": ignoree.ignored_at,
    }

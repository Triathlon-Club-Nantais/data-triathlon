"""Rapprochement automatique de deux `Course` qui désignent la même épreuve (#289).

Règle R, mesurée par le sondage #277
(`docs/superpowers/specs/2026-08-12-sources-multiples-epreuve-sondage.md`), qui
**prime** sur ce module : toute divergence future se tranche en re-sondant, pas
en assouplissant ici. Deux `Course` sont la même épreuve si et seulement si :

1. `provider` de chacune ∈ `{"klikego", "breizhchrono"}` ;
2. `platform_event_id(source_url)` est **non vide** et **égal** des deux côtés ;
3. `heat_slug(source_url)` est **non vide** et **égal** des deux côtés.

Aucune tolérance, aucun repli, aucun score. Mesuré à **0 faux positif** sur
4465 paires de la base de dev à cette précision exacte ; la moindre souplesse
assouplie (nom normalisé, millésime retiré, suffixe de heat retiré, ±3 jours
sur la date) en fait apparaître de 37 à 53 — le sur-outillage est ici le seul
risque, pas l'insuffisance.

Le vrai bénéficiaire n'est **pas** Klikego ↔ Breizh Chrono classique : ces deux
fournisseurs partagent le même back-office et collident déjà sur l'identité
actuelle (`name, event_date, event_type, is_relay`), donc `get_or_create` les
fusionne sans l'aide de ce module — #283 s'occupe d'enregistrer la seconde URL.
Le cas qui a réellement besoin d'un rapprochement automatique est **l'inter-
façade Breizh Chrono** (`live.` ↔ `resultats.`), qui diverge sur le nom et sur
la date (jusqu'à 2 jours) mais partage le même identifiant de plateforme et le
même slug de heat.
"""
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.course import Course
from app.repositories import course_source_repository
from app.scrapers.breizhchrono import _parse_bc_url, _parse_live_url
from app.scrapers.registry import KlikegoProvider

#: Les deux seuls fournisseurs qui partagent un identifiant de plateforme
#: (mesuré sur les 14 modules de `scrapers/` — cf. Q2 du sondage #277).
RECONCILABLE_PROVIDERS = ("klikego", "breizhchrono")


def _is_breizhchrono_live(url: str) -> bool:
    """Façade `live.` ou `resultats.`/`coureur.jsp` — même dispatch que `registry.BreizhChronoProvider`."""
    return "live.breizhchrono.com" in urlparse(url).netloc.lower()


def platform_event_id(provider: str, url: str) -> str:
    """L'identifiant de plateforme **entier** (suffixe d'édition compris), ou vide.

    Ne jamais tronquer au préfixe `{epoch_ms}` : c'est une clé de **compte**
    chez la plateforme, pas d'événement — 12 préfixes sur 40 mesurés dans le
    Sheet du club portent plusieurs éditions, l'un en porte 8 sans rapport.
    """
    if provider == "klikego":
        event_id, _heat, _slug, _name = KlikegoProvider._parse_url(url)
        return event_id
    if provider == "breizhchrono":
        if _is_breizhchrono_live(url):
            reference, _heat = _parse_live_url(url)
            return reference
        event_id, _heat, _slug = _parse_bc_url(url)
        return event_id
    return ""


def heat_slug(provider: str, url: str) -> str:
    """Le slug du heat, en minuscules, ou vide.

    Comparé **octet par octet après `lower()`** par l'appelant — jamais
    normalisé davantage : le triple tiret est porteur de sens
    (`_detect_relay` teste `heat_slug.endswith("---")`), et
    `duathlon-s---open` ≠ `duathlon-s---en-relais`.
    """
    if provider == "klikego":
        _event_id, heat, _slug, _name = KlikegoProvider._parse_url(url)
        return heat.lower()
    if provider == "breizhchrono":
        if _is_breizhchrono_live(url):
            _reference, heat = _parse_live_url(url)
            return heat.lower()
        _event_id, heat, _slug = _parse_bc_url(url)
        return heat.lower()
    return ""


def find_reconcilable_course(db: Session, *, provider: str, source_url: str) -> Course | None:
    """Une `Course` existante qui partage `(platform_event_id, heat_slug)`, ou `None`.

    Ne compare **jamais** `name`/`event_date`/`event_type`/`is_relay` : les
    quatre sont mesurés inaptes par le sondage #277 (granularité de nommage
    différente selon la façade, date parfois fausse de 1 à 2 jours).
    """
    if provider not in RECONCILABLE_PROVIDERS:
        return None
    event_id = platform_event_id(provider, source_url)
    heat = heat_slug(provider, source_url)
    if not event_id or not heat:
        return None
    for source in course_source_repository.list_by_providers(db, RECONCILABLE_PROVIDERS):
        if (
            platform_event_id(source.provider, source.url) == event_id
            and heat_slug(source.provider, source.url) == heat
        ):
            return source.course
    return None

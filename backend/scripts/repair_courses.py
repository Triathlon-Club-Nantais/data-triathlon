#!/usr/bin/env python3
"""
repair_courses.py — Répare les courses dont les métadonnées sont fausses.

Deux dégâts hérités d'imports antérieurs aux correctifs des scrapers :

  A. **Nom** — Klikego / Breizh Chrono dérivaient le nom du slug de l'URL, qui
     perd accents, esperluettes et casse (« Run  Bike De Fay De Bretagne »), et
     qu'une URL `coureur.jsp` ne porte pas du tout (course sans nom). Le nom
     vient désormais du `<title>` de la page. Seule la colonne `name` change :
     on la met à jour **en place**, sans toucher aux participations.

  B. **Date** — les scrapers Wiclax / TimePulse ne lisaient qu'une date ISO,
     absente des fichiers anciens. Ici l'identité de la course
     `(nom, date, type)` change : un simple UPDATE créerait un doublon au
     prochain import. On **réimporte** l'épreuve (les scrapers corrigés créent
     les courses datées), puis on **supprime** les courses restées orphelines
     (celles que le réimport n'a pas touchées).

Le script est idempotent : une base déjà saine ne subit aucune écriture.

Usage :
    cd backend
    python scripts/repair_courses.py --dry-run   # ce qui serait fait
    python scripts/repair_courses.py             # applique
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.models.course import Course  # noqa: E402
from app.scrapers.klikego_platform import parse_event_name  # noqa: E402
from app.services import import_service  # noqa: E402

# Fronts dont le nom d'épreuve se lit dans le <title> (moteur Klikego partagé).
_TITLE_PROVIDERS = ("klikego", "breizhchrono")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _heat_of(url: str, final_url: str) -> str:
    """Heat porté par l'URL, ou celui vers lequel la page nous a redirigés.

    Breizh Chrono préfixe son `<title>` du libellé du heat ; il faut le connaître
    pour l'ôter. Une URL d'événement sans heat redirige vers son premier heat,
    dont le slug est le dernier segment du chemin d'arrivée.
    """
    m = re.search(r"[?&]heat=([^&]+)", url)
    if m:
        return m.group(1)
    parsed = urlparse(final_url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    # /resultats-courses/{slug}-{event_id}/{heat}
    if len(parts) >= 3 and parts[0] == "resultats-courses":
        return parts[2]
    return ""


def _results_page(url: str) -> str:
    """Page de résultats correspondant à une URL d'import.

    Une URL Breizh Chrono `coureur.jsp` (fiche d'un coureur) sert un titre
    générique, sans nom d'épreuve : on la traduit en page de heat, comme le fait
    le scraper. Le slug manquant n'empêche rien, BC redirige sur le bon.
    """
    if "coureur.jsp" in url:
        from app.scrapers.breizhchrono import BASE, _parse_bc_url

        event_id, heat, slug = _parse_bc_url(url)
        return f"{BASE}/resultats-courses/{slug}-{event_id}/{heat}"
    return url


def _name_from_page(url: str) -> str:
    """Nom d'épreuve publié par la page de résultats ; `""` si illisible."""
    page_url = _results_page(url)
    try:
        with httpx.Client(follow_redirects=True, timeout=30, headers=_HEADERS) as client:
            resp = client.get(page_url)
            if resp.status_code != 200:
                return ""
            return parse_event_name(resp.text, _heat_of(page_url, str(resp.url)))
    except httpx.HTTPError:
        return ""


def repair_names(db, *, dry_run: bool) -> int:
    """Passe A — aligne le nom des courses Klikego / BC sur celui de leur page."""
    courses = (
        db.query(Course)
        .filter(Course.provider.in_(_TITLE_PROVIDERS))
        .order_by(Course.id)
        .all()
    )
    # Le nom d'épreuve ne dépend que de la page : une requête par URL suffit,
    # même quand plusieurs heats (donc plusieurs courses) la partagent.
    by_url: dict[str, list[Course]] = {}
    for course in courses:
        if "live.breizhchrono.com" in course.source_url:
            continue  # front non supporté par les scrapers (pas de page lisible)
        by_url.setdefault(course.source_url, []).append(course)

    renamed = 0
    for url, group in by_url.items():
        name = _name_from_page(url)
        if not name:
            print(f"  ⚠ nom illisible sur la page : {url}")
            continue
        for course in group:
            if course.name == name:
                continue
            print(f"  #{course.id} « {course.name} » → « {name} »")
            if not dry_run:
                course.name = name
            renamed += 1
    if not dry_run:
        db.commit()
    return renamed


def repair_dates(db, *, dry_run: bool) -> tuple[int, int]:
    """Passe B — réimporte les épreuves sans date, puis purge les courses orphelines.

    Renvoie (épreuves réimportées, courses supprimées).
    """
    urls = [
        url
        for (url,) in db.query(Course.source_url)
        .filter(Course.event_date.is_(None))
        .distinct()
        .all()
    ]
    if dry_run:
        for url in urls:
            stale = db.query(Course).filter(
                Course.source_url == url, Course.event_date.is_(None)
            ).count()
            print(f"  réimport de {url} ({stale} course(s) sans date à remplacer)")
        return len(urls), 0

    settings = get_settings()
    reimported = deleted = 0
    for url in urls:
        started = utcnow()
        try:
            out = import_service.import_event(db, url, settings, force=True)
        except Exception as exc:  # noqa: BLE001 — une épreuve KO ne doit pas tout arrêter
            print(f"  ✗ {url} : {exc}")
            continue
        reimported += 1
        # Les courses de cette URL que le réimport n'a pas touchées portent
        # l'ancienne identité (sans date) : plus rien ne les alimentera.
        stale = (
            db.query(Course)
            .filter(Course.source_url == url, Course.scraped_at < started)
            .all()
        )
        for course in stale:
            print(f"  – suppression #{course.id} « {course.name} » ({course.event_date})")
            db.delete(course)
            deleted += 1
        db.commit()
        print(f"  ✓ {url} — {out['imported']} participation(s) importée(s)")
    return reimported, deleted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="n'écrit rien")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("A. Noms d'épreuve (Klikego / Breizh Chrono) — mise à jour en place")
        renamed = repair_names(db, dry_run=args.dry_run)
        print(f"   {renamed} course(s) renommée(s)\n")

        print("B. Épreuves sans date (Wiclax / TimePulse) — réimport puis purge")
        reimported, deleted = repair_dates(db, dry_run=args.dry_run)
        print(f"   {reimported} épreuve(s) réimportée(s), {deleted} course(s) supprimée(s)")
    finally:
        db.close()

    if args.dry_run:
        print("\n(dry-run : aucune écriture)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Re-scrape en masse des épreuves déjà en base (force=True, bypass du cache TTL).

Unité de travail : l'**épreuve**, c'est-à-dire une **source active** unique — et
non la course. La table `course` en porte N par épreuve (heats Breizh Chrono,
variantes individuel/relais) ; un seul scrape d'épreuve les réimporte toutes.
Compteurs et `--limit` raisonnent donc en épreuves (cf. `_dedupe_par_url`).

**Les sources passives ne sont jamais scrapées** (#282) : ni par la sélection en
base, ni par un ciblage explicite, qui leur substitue l'active de leur épreuve —
sauf quand celle-ci n'en a aucune, la passive étant alors la seule publication
connue. C'est la fin des doublons que
`rescrape-db` fabriquait : deux publications d'une même course réelle étaient
deux lignes `Course` sans lien, donc deux scrapes, donc deux classements
concurrents. Contrepartie assumée : une source passive vieillit indéfiniment —
elle ne sert qu'à documenter l'autre publication et à permettre la bascule
(#285), qui re-scrape sur son point de bascule.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.course import Course
from app.repositories import athlete_repository, course_repository, course_source_repository
from app.services import sheet_source
from app.services.batch import (
    BatchFailure,
    BatchItem,
    copy_totals,
    est_echec_total,
    run_batch,
)
from app.services.import_service import PassiveSource
from app.services.progress import ProgressReporter


def _dedupe_par_url(courses: list[Course]) -> list[Course]:
    """Une épreuve par URL de source **active**, en gardant la première course vue.

    `course.source_url` est l'URL de la source active (#279), et `iter_all` ne rend
    plus que des courses qui en ont une (#282) : la clé de dédup est donc l'URL
    qu'on va effectivement interroger, jamais une passive.

    Une même URL porte souvent **plusieurs** courses : heats auto-découverts de
    Breizh Chrono, variantes individuel/relais de wiclax/timepulse… Or un seul
    scrape d'épreuve les réimporte toutes. Sans dédup, on scraperait la même URL
    N fois (base de dev : 53 courses pour 12 URLs, dont une portée par 13 heats)
    — requêtes inutiles vers les sites tiers, `skipped` et `errors` gonflés d'un
    facteur N, et `--limit` qui ne bornerait plus des épreuves mais des courses.

    Clé de dédup : `sheet_source.normalize_url`, par symétrie avec `dedupe_links`
    de l'import de masse. Ces URLs viennent de la DB (donc des scrapers, pas
    d'une saisie manuelle) : la normalisation est ici quasi neutre, elle ne fait
    que rattraper les écarts de casse d'hôte ou de slash final entre deux
    providers. La course retenue fournit le libellé `provider · name`.
    """
    uniques: dict[str, Course] = {}
    for course in courses:
        uniques.setdefault(sheet_source.normalize_url(course.source_url), course)
    return list(uniques.values())


def _items_depuis_urls(db: Session, urls: list[str]) -> list[BatchItem]:
    """Épreuves ciblées **explicitement** : la base ne sert plus qu'à libeller.

    Une URL inconnue en base est le cas **nominal** du rejeu d'un échec
    d'import : l'épreuve fautive n'a rien persisté, elle est absente de la table
    `course`. La sélectionner via `iter_all` porterait sur zéro épreuve et
    sortirait en code 0 — un silence trompeur. On soumet donc les URLs telles
    quelles au batch, connues ou non.

    Le libellé est purement cosmétique (ligne de progression) : quand la course
    est inconnue, il retombe sur l'URL, sans avertissement ni dégradation.
    """
    items: list[BatchItem] = []
    for url in sheet_source.dedupe_links(urls):
        course = course_repository.get_latest_by_source_url(db, url)
        label = f"{course.provider} · {course.name}" if course else url
        items.append(BatchItem(url=url, label=label))
    return items


@dataclass(frozen=True)
class PassiveTarget:
    """Une URL ciblée qui n'est qu'une source **passive** : à rediriger (#282).

    Porte de quoi écrire la substitution, et rien de plus — c'est la CLI qui la
    formule et l'applique (`cli/commands/rescrape_db`), seule à connaître le
    canal d'affichage.

    `active_url` peut être vide, et ce n'est pas un cas dégradé : une épreuve
    saisie à la main n'a aucune source active, et rattacher une URL à celle-ci
    (#283) produit exactement une passive orpheline. Il n'y a alors rien vers
    quoi rediriger, et c'est la passive elle-même qui est scrapée.
    """
    #: L'URL telle que l'opérateur l'a écrite — c'est celle-là qu'il doit retrouver.
    url: str
    course_name: str
    active_url: str


def find_passive_targets(db: Session, urls: list[str]) -> list[PassiveTarget]:
    """Parmi ces URLs ciblées, celles qu'aucune épreuve ne tient pour active (#282).

    Le ciblage explicite (`--url`, `--urls-from`) court-circuite la base : c'est
    ce qui permet de rejouer un échec d'import, dont l'épreuve n'a rien persisté.
    Ce court-circuit a un angle mort — une URL **connue mais passive** serait
    scrapée « à côté », et importerait le classement d'un autre chronométreur
    dans l'épreuve, soit le doublon que la table des sources existe pour
    supprimer. On les signale donc en amont du batch, pour que l'appelant leur
    substitue l'active de leur épreuve.

    Trois réponses, et la distinction est tout l'objet de la fonction :

    - URL **absente** de `course_sources` → laissée passer. Cas nominal du rejeu.
    - URL **active** sur au moins une épreuve → laissée passer, et l'épreuve où
      elle est active est celle qui sera réimportée. Rien n'interdit qu'une même
      URL soit l'active de l'une et la passive d'une autre : une URL porte
      légitimement N épreuves (heats Klikego, catégories Wiclax).
    - URL **connue et passive partout** → rendue, en nommant la première épreuve
      qui la porte et l'URL active de celle-ci.

    Comparaison sur `sheet_source.normalize_url`, comme partout ailleurs : un
    slash final ou une casse d'hôte vient d'un copier-coller, pas d'une intention,
    et comparer les formes brutes ferait passer la passive au travers du garde-fou.
    D'où le `IN` élargi à la forme normalisée de chaque cible — les URLs stockées
    viennent des scrapers, donc sont déjà quasi normalisées, et c'est ce qui rend
    ce doublement suffisant.

    Ordre d'entrée conservé : c'est l'ordre du fichier de l'opérateur, donc celui
    dans lequel il corrigera.
    """
    if not urls:
        return []

    recherchees = {forme for url in urls for forme in (url, sheet_source.normalize_url(url))}
    par_url: dict[str, list] = defaultdict(list)
    for source in course_source_repository.list_by_urls(db, sorted(recherchees)):
        par_url[sheet_source.normalize_url(source.url)].append(source)

    refuses: list[PassiveTarget] = []
    for url in urls:
        portees = par_url.get(sheet_source.normalize_url(url), [])
        if not portees or any(source.is_active for source in portees):
            continue
        course = portees[0].course
        refuses.append(
            PassiveTarget(url=url, course_name=course.name, active_url=course.source_url)
        )
    return refuses


@dataclass(frozen=True)
class IdentiteReconciliee:
    """Une identité corrigée et son volume : « ancien -> nouveau (N participations) ».

    Agrégée par paire (ancien, nouveau) : bornée aux seules réconciliations,
    donc légère — comme `failures`. Reprise telle quelle dans `--json` via
    `asdict()`.
    """
    ancien: str
    nouveau: str
    participations: int


@dataclass
class RescrapeOutcome:
    """Bilan d'un rescrape-db. `total` = nombre d'**épreuves** (URLs uniques).

    `total`, `processed` et `errors` comptent des **épreuves** ; `imported`,
    `updated` et `skipped`, des **participants**. Le rapport texte nomme ces
    unités.
    """
    total: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    #: Épreuves réellement traitées — égal à `total`, sauf sous Ctrl-C.
    processed: int = 0
    dry_run_urls: list[str] = field(default_factory=list)
    interrupted: bool = False
    #: Épreuves fautives (URL + cause). Borné aux seuls échecs : léger,
    #: contrairement à la liste de toutes les épreuves. `asdict()` l'embarque
    #: dans `--json`, ce qui referme la boucle de rejeu sans fichier d'état.
    failures: list[BatchFailure] = field(default_factory=list)
    #: Participations réconciliées (identité réassignée).
    reconciled: int = 0
    #: Athlètes fusionnés (cible corrigée préexistante — pas un simple renommage).
    merged: int = 0
    #: Athlètes orphelins supprimés en fin de batch (fiches vidées).
    orphans_removed: int = 0
    #: Dry-run : le batch a scrapé sans persister. Neutralise `echec_total`.
    dry_run: bool = False
    #: Détail des identités réconciliées (ancien -> nouveau, volume).
    reconciliations: list[IdentiteReconciliee] = field(default_factory=list)
    #: URLs enregistrées en sources passives d'une épreuve déjà connue (#283).
    #: Rare ici — le mode base re-scrape des URLs déjà actives — mais pas
    #: impossible : un fan-out peut publier une URL de heat déjà connue ailleurs.
    passive_sources: list[PassiveSource] = field(default_factory=list)

    @property
    def echec_total(self) -> bool:
        """Toutes les épreuves ciblées ont échoué (cf. `batch.est_echec_total`).

        `total` est le nombre d'épreuves soumises au batch (URLs uniques, après
        `--limit`) : c'est à lui qu'`errors` se compare.

        Un dry-run ne persiste rien : il ne peut jamais être un échec total, même
        si des scrapes échouent (règle « un dry-run sort toujours en 0 »).

        Propriété (et non champ) : `asdict()` ne sérialise que les champs, la
        charge utile `--json` reste inchangée.
        """
        if self.dry_run:
            return False
        return est_echec_total(epreuves=self.total, errors=self.errors)


def run_rescrape_db(
    db: Session,
    settings: Settings,
    *,
    dry_run: bool = False,
    older_than: int | None = None,
    provider: str | None = None,
    limit: int | None = None,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
    urls: list[str] | None = None,
    single_heat: bool = False,
) -> RescrapeOutcome:
    """Re-scrape toutes les épreuves en DB avec force=True (bypass du cache TTL).

    Ne retient que les courses ayant une source **active** — la jointure d'
    `iter_all` s'en charge (#282) —, puis dédoublonne par URL : on raisonne en
    **épreuves à scraper**, pas en courses. `limit` borne donc les épreuves, et
    s'applique **après** la dédup. En dry-run : liste les URLs sans scraper ni
    persister.

    Deux modes de sélection, un seul batch en aval. `urls=None` : les épreuves
    viennent de la base (`provider`, `older_than`, dédup par URL). `urls`
    fourni : la base **n'est pas interrogée pour sélectionner**, chaque URL
    devient une épreuve — c'est ce qui permet de rejouer un échec d'import, dont
    l'épreuve n'existe pas en base. `limit` borne la liste finale dans les deux
    cas ; `force=True`, `delay`, dry-run et Ctrl-C sont inchangés.
    """
    if urls is not None:
        items = _items_depuis_urls(db, urls)
    else:
        # Pas de second filtre sur `source_url` : `iter_all` joint la source
        # active, donc chaque course rendue en a une par construction (#282).
        courses = course_repository.iter_all(
            db, provider=provider, older_than_days=older_than
        )
        epreuves = _dedupe_par_url(courses)
        # Le nom de la course vient de la DB : on peut libeller proprement.
        items = [
            BatchItem(url=c.source_url, label=f"{c.provider} · {c.name}")
            for c in epreuves
        ]
    if limit is not None:
        items = items[:limit]

    outcome = RescrapeOutcome(total=len(items), dry_run=dry_run)
    if dry_run:
        # Charge utile réservée au dry-run : hors dry-run, embarquer l'URL de
        # chaque épreuve gonflerait la sortie --json de plusieurs dizaines de Ko.
        outcome.dry_run_urls = [item.url for item in items]

    totals = run_batch(
        db, items, settings, force=True, persist=not dry_run, delay=delay, reporter=reporter,
        single_heat=single_heat,
    )

    copy_totals(outcome, totals)

    outcome.reconciled = totals.reconciled
    outcome.merged = len({r.ancien for r in totals.reassignments if r.fusion})
    compteur = Counter((r.ancien, r.nouveau) for r in totals.reassignments)
    outcome.reconciliations = [
        IdentiteReconciliee(ancien=ancien, nouveau=nouveau, participations=n)
        for (ancien, nouveau), n in compteur.items()
    ]

    # Nettoyage des orphelins : une seule fois, après tout le batch, et jamais en
    # dry-run (rien n'a été persisté, donc aucune fiche n'a été vidée).
    if not dry_run:
        outcome.orphans_removed = athlete_repository.delete_orphans(db)
        db.commit()

    return outcome

"""Persistance d'un import : des résultats déjà scrapés vers la base (#914, #1186).

Seul point d'entrée : `persist_steps`, et `persist_results` qui l'épuise. Les
rattrapages de lot (datation #972, classification #294, réidentification,
renumérotations #757, #785 et #672) passent avant la première ligne écrite.
Ne clôt jamais la transaction : l'appelant commite ou annule.
"""
import logging
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, replace

from sqlalchemy.orm import Session

from app.core.athlete_identity import athlete_identity_keys
from app.core.club import canonical_club_key, is_significant_club
from app.core.gender import normalize_gender
from app.core.identity import identity_hash
from app.core.text import deaccent
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.course_source import CourseSource
from app.models.participation import Participation
from app.repositories import (
    absorbed_course_repository,
    admin_action_log_repository,
    athlete_alias_repository,
    athlete_known_club_repository,
    athlete_repository,
    club_alias_repository,
    course_repository,
    course_source_repository,
    ignored_athlete_pair_repository,
    lock_repository,
    opposition_repository,
    participation_repository,
    tcn_count_repository,
)
from app.repositories.athlete_repository import IdentityKey
from app.scrapers import registry
from app.scrapers.base import (
    STATUS_DNF,
    STATUS_DNS,
    STATUS_DSQ,
    STATUS_FINISHER,
    ScrapedResult,
)
from app.scrapers.utils import heat_is_challenge, is_masked_name, split_relay_teammates, to_seconds
from app.services import challenge_service, course_reconciliation, mapping, quality
from app.services.challenge_service import ChallengeRow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reassignment:
    """Une identité réconciliée : ancienne graphie → nouvelle, et sa nature.

    `fusion` = True quand la cible corrigée préexistait (deux fiches en une),
    False quand elle vient d'être créée (simple renommage). Labels figés à la
    réassignation : ils survivent au rollback d'un dry-run.
    """
    ancien: str
    nouveau: str
    fusion: bool


@dataclass(frozen=True)
class PassiveSource:
    """Une URL enregistrée comme source **passive** d'une épreuve déjà connue (#283).

    Ni une erreur, ni un import : rien n'a échoué, et rien n'a été ajouté au
    classement. C'est un fait à rapporter — même forme que `BatchFailure` (url,
    libellé, message) pour qu'un seul objet serve le SSE, le `--json` et le
    bilan texte de la CLI.

    Le message est figé ici, à l'endroit qui connaît le nom de l'épreuve : plus
    haut, le bilan de batch n'aurait plus que des URLs à recoller entre elles.
    """
    url: str
    course_name: str
    message: str


def _identite(athlete) -> str:
    """Libellé d'identité pour le bilan : « NOM | Prénom »."""
    return f"{athlete.nom} | {athlete.prenom}"


#: Clés d'appariement / d'identité : jamais réécrites par la fusion prudente.
#: `athlete_id` en fait partie — la réconciliation d'identité (#66) est un axe
#: séparé, traité par `_Persister._reconcile_resolved`, pas par ce rafraîchissement de
#: valeurs : les deux s'appliquent à la suite sans jamais écrire les mêmes champs.
_CLES_APPARIEMENT = frozenset({"athlete_id", "course_id", "bib_number"})


def _is_empty(value: object) -> bool:
    """Vide au sens de la fusion prudente : `None`, chaîne vide, dict vide.

    `False` et `0` n'en sont **pas** : un `is_relay=False` est une affirmation du
    scraper, pas une absence, et doit pouvoir corriger un `True` erroné. Un test
    de vérité pythonien (`if value:`) confondrait les deux — d'où l'égalité
    explicite, qui distingue `False`/`0` de `""`/`{}` (`False == {}` est faux).
    """
    return value is None or value == "" or value == {}


def _merge_fields(existing, fields: dict) -> dict:
    """Champs à écrire : source non vide ET différente de la base.

    `status` est exclu ici (traité par `_resolve_status`, car jamais vide) ; les
    clés d'appariement aussi. Comparer avant d'écrire évite des `UPDATE` inutiles
    sur des milliers de lignes inchangées et distingue `updated` de `skipped`.
    """
    changes = {}
    for key, value in fields.items():
        if key in _CLES_APPARIEMENT or key == "status":
            continue
        # `raw_data` est la ligne source du moment, pas une valeur à préserver :
        # vide, elle remplace quand même l'ancienne, sans quoi une colonne que la
        # source ne publie plus y survivait (#1200).
        if _is_empty(value) and key != "raw_data":
            continue
        if getattr(existing, key) != value:
            changes[key] = value
    return changes


def _resolve_status(existing, scraped: ScrapedResult, changes: dict) -> str:
    """Statut fusionné. Un statut explicite du scraper écrase ; sinon on le
    re-dérive du `total_time` **fusionné** (base + écrasement éventuel), jamais du
    scrapé seul : une source ayant perdu le temps ne doit pas basculer un
    finisher en DNF alors que le temps, lui, survit (vide n'écrase pas).
    """
    if scraped.status:
        return scraped.status
    merged_total = changes.get("total_time", existing.total_time)
    return STATUS_FINISHER if merged_total else STATUS_DNF


_NON_FINISHER_STATUSES = frozenset({STATUS_DNS, STATUS_DNF, STATUS_DSQ})


_NON_FINISHER_FIELDS = ("rank_overall", "rank_category", "rank_gender", "total_time")


def _non_finisher_overrides(existing, scraped: ScrapedResult, fields: dict) -> dict:
    """Exception à « vide n'écrase pas » (#962) : sur un statut non-finisher
    **explicite**, le scraper vide volontairement rangs et temps (et les splits
    d'un DNS). Sa valeur, vide comprise, fait alors foi ; sinon un rescrape ne
    corrigerait jamais une ligne importée avant ce vidage.
    """
    if scraped.status not in _NON_FINISHER_STATUSES:
        # Un total illisible en base (« Abandon », #969) n'est pas une valeur à protéger.
        if existing.total_time and mapping.parse_duration(existing.total_time) is None:
            return {"total_time": fields["total_time"]}
        return {}
    keys = _NON_FINISHER_FIELDS + (("splits",) if scraped.status == STATUS_DNS else ())
    return {key: fields[key] for key in keys if getattr(existing, key) != fields[key]}


#: Taille de la tranche de résolution par lot (#706) : au-delà, une course
#: déclenche sa résolution d'athlètes avant la fin du scrape plutôt que
#: d'accumuler une file sans borne. Ordre de grandeur repris de l'audit
#: source (`research.md` de la feature #706) — un détail d'implémentation,
#: pas un critère d'acceptation.
_TRANCHE_SIZE = 500


def _team_key(team_name: str | None) -> str:
    """Nom d'équipe comparable d'un scrape à l'autre : casse, accents et espaces ignorés."""
    return " ".join((deaccent(team_name) or "").lower().split())


def _identity_key(scraped: ScrapedResult) -> IdentityKey:
    """Clé d'identité d'une ligne scrapée, celle que stockent les fiches (#907)."""
    return _pair_key((scraped.athlete_name, scraped.athlete_firstname))


def _pair_key(pair: tuple[str | None, str | None]) -> IdentityKey:
    """Une paire sans identité (`-`) garde sa graphie brute comme clé en mémoire :
    elle ne correspond à aucune fiche et n'en partage aucune avec une autre
    paire. `add` a déjà renommé ou écarté les lignes dans ce cas ; ne restent
    que des équipiers de relais."""
    key = athlete_identity_keys(*pair)
    return key if key[0] is not None else (None, "|".join(part or "" for part in pair))


def _source_key(scraped: ScrapedResult) -> str | None:
    """Clé source d'une ligne (`<nom>|<prénom>`, #896), celle que retient
    `Participation.source_identity_key`."""
    last_name_key, first_name_key = athlete_identity_keys(scraped.athlete_name, scraped.athlete_firstname)
    return None if last_name_key is None else f"{last_name_key}|{first_name_key}"


def _stored_source_key(participation: Participation) -> str | None:
    """Un résultat saisi à la main n'a pas de clé source : celle de sa fiche en tient lieu."""
    if participation.source_identity_key is not None:
        return participation.source_identity_key
    athlete = participation.athlete
    return None if athlete.last_name_key is None else f"{athlete.last_name_key}|{athlete.first_name_key}"


def _participation_fields(scraped: ScrapedResult, *, athlete_id: int, course_id: int) -> dict:
    return {
        **mapping.participation_fields(scraped, athlete_id=athlete_id, course_id=course_id),
        "source_identity_key": _source_key(scraped),
    }


def _published_name(scraped: ScrapedResult) -> str:
    """Nom publié d'une ligne, reconstitué depuis la coupe nom/prénom du scraper.

    Même formule que le nom d'équipe posé par `set_teammates` (#894) : la clé
    d'appariement sans dossard (`_team_key`) reste stable d'un scrape à l'autre.
    """
    return " ".join(filter(None, [scraped.athlete_name, scraped.athlete_firstname]))


def _proposed_teammates(scraped: ScrapedResult) -> tuple[tuple[str, str], ...] | None:
    """Équipiers nommés d'une ligne de relais (#895) ; jamais hors relais (#63)."""
    if not scraped.is_relay:
        return None
    teammates = split_relay_teammates(_published_name(scraped))
    return tuple(teammates) if teammates else None


def _oriented_teammates(
    teammates: tuple[tuple[str, str], ...], found: dict[IdentityKey, Athlete]
) -> tuple[tuple[str, str], ...]:
    """Tout en majuscules, « PRÉNOM NOM » se lit « NOM PRÉNOM » (klikego) : une
    fiche connue à l'envers, et pas à l'endroit, tranche l'ordre."""
    return tuple(
        pair[::-1] if _pair_key(pair) not in found and _pair_key(pair[::-1]) in found else pair
        for pair in teammates
    )


@dataclass(frozen=True)
class _PendingResolution:
    """Une ligne en attente de résolution d'athlète par lot (#706), mise en
    file plutôt que résolue immédiatement par `add()`.

    `participation` porte la ligne déjà appariée par dossard à réconcilier
    (chemin `_reconcile`) ; `None` pour une participation neuve à créer
    (chemin dossard neuf ou sans dossard — `bib` distingue les deux, `None`
    valant « sans dossard », pour rejouer `_match_without_bib`/les crédits
    une fois l'athlète connu).
    """
    scraped: ScrapedResult
    bib: str | None
    participation: Participation | None
    teammates: tuple[tuple[str, str], ...] | None = None
    reconcile_blocked: bool = False


class _Persister:
    """Persiste les résultats scrapés en **upsert**, avec déduplication.

    Point de persistance unique des trois entrées (rescrape-db, import-sheet, web
    SSE). Deux clés d'appariement, par course :
      - le dossard, quand il existe (`uq_participation_bib`) ;
      - sinon la clé source de la ligne (`source_identity_key`, #896), en
        **multiset** — mais la mise à jour ne s'applique que si la clé n'a qu'une
        seule participation sur la course (cf. `add`).

    Une ligne appariée est **fusionnée prudemment** (`_merge_fields`) : la source
    ne réécrit que ses valeurs non vides. `athlete_id` échappe à cette fusion —
    seule la **réconciliation d'identité** (`_reconcile_resolved`, sur le chemin
    dossard) le réassigne, quand la clé source a changé, et jamais sur un
    résultat verrouillé par un admin (`athlete_locked`).
    """

    def __init__(self, db: Session, event_url: str):
        self.db = db
        self.event_url = event_url
        # Empreintes des personnes opposées (#334), lues une fois : chaque ligne se teste en mémoire.
        self._opposed: set[str] = opposition_repository.all_hashes(db)
        self._by_bib: dict[int, dict[str, Participation]] = {}
        self._added_bibs: dict[int, set[str]] = {}
        self._duplicate_bibs: Counter[int] = Counter()
        self._excluded_ranks: defaultdict[int, set[int]] = defaultdict(set)
        # Lignes sans dossard par clé source (#896) : une ligne réattribuée par un
        # admin se retrouve ainsi sans que sa fiche d'origine soit recréée.
        self._without_bib: dict[int, dict[str | None, list[Participation]]] = {}
        self._teams_without_bib: dict[int, dict[str, list[Participation | None]]] = {}
        # Garde des relais découpés (#895, FR-010) : un coureur ne figure qu'une
        # fois par course. Les ids couvrent la base, les clés d'identité les
        # équipiers de ce scrape, qui n'ont pas encore d'id quand on décide.
        self._present_ids: dict[int, set[int]] = {}
        self._reserved_keys: dict[int, set[IdentityKey]] = {}
        # Lignes à découper, résolues après toutes les autres lignes de la course
        # (`finalize`) : la garde voit ainsi chaque coureur de la course, quelle
        # que soit la tranche où il apparaît.
        self._pending_splits: dict[int, list[_PendingResolution]] = {}
        self._credits: dict[int, dict[str | None, int]] = {}
        self._updated_single: dict[int, set[str | None]] = {}
        self._courses: dict[int, Course] = {}
        #: Changements de club et de genre, appliqués une fois par `finalize` (#980).
        self._athlete_updates: dict[int, tuple[Athlete, dict[str, str]]] = {}
        # Cache de résolution de course par lot (#759) : sans lui, `add()`
        # rappelle `mapping.get_or_create_course` (3 requêtes DB minimum) à
        # chaque participation, même quand tout le lot appartient à la même
        # course — mesuré à ~7000 requêtes sur une course à 2396 participants.
        # Clé = les deux axes dont dépend la course résolue : la réconciliation
        # par URL (`provider`, `source_url`) et l'identité stricte
        # (`uq_course_identity` : nom, date, type, relais) — une seule URL peut
        # faire fan-out sur plusieurs heats au sein d'un même lot (#156), donc
        # `(provider, url)` seul collapserait des courses distinctes.
        self._course_resolutions: dict[tuple, mapping.CourseResolution] = {}
        # Identités d'épreuves absorbées par fusion, lues une fois par lot (#983).
        self._absorbed: dict[tuple, bool] = {}
        # Résolution par lot (#706) : lignes en attente et participations
        # connues d'une course, par `course_id` — `_participations` remplace
        # le second `list_for_course` de `finalize()` (cf. `_index_course`).
        self._pending: dict[int, list[_PendingResolution]] = {}
        self._participations: dict[int, list[Participation]] = {}
        self.imported = 0
        self.updated = 0
        self.skipped = 0
        self.reconciled = 0
        self.challenges = 0
        self.reassignments: list[Reassignment] = []
        # Fiches qui ont perdu un résultat par réconciliation : leur verdict du club se recalcule (#1206).
        self._previous_athlete_ids: set[int] = set()
        # Lignes dont le repli d'identité a trouvé plusieurs fiches (#908) : une
        # fiche est créée, rien n'est deviné, l'admin tranche.
        self.ambiguous_identities: list[dict] = []
        # Fiches d'homonyme créées parce qu'une fiche portait déjà un autre dossard
        # de la même épreuve individuelle (#967).
        self.homonyms_created: list[dict] = []
        self._bibs_by_athlete: dict[int, dict[int, set[str]]] = {}
        # Clé d'identité publiée pour chaque dossard de ce scrape : un dossard
        # d'une fiche ne signale un homonyme que s'il court encore sous ce nom.
        self._bib_keys: dict[int, dict[str, IdentityKey]] = {}
        # Fiches créées par `_athlete_for_bib` (homonyme ou principale d'une clé
        # trouvée par repli) : s'y rattacher est une création, pas une fusion.
        self._created_for_bibs: set[int] = set()
        # Signal de club (#1209) : alias lus une fois, et l'homonyme choisi pour
        # chaque couple (clé d'identité, club) de ce scrape.
        self._club_aliases: dict[str, str] = club_alias_repository.canonical_map(db)
        self._club_homonyms: dict[tuple[IdentityKey, str], Athlete] = {}
        # Dédup par `id` de source, pas par ligne scrapée : `add` résout l'épreuve
        # une fois par participant, un classement de 250 lignes rendrait sinon
        # 250 fois la même phrase et ferait compter 250 sources pour une.
        self._passive: dict[int, PassiveSource] = {}

    @property
    def passive_sources(self) -> list[PassiveSource]:
        """Les sources passives rencontrées, dans l'ordre de première rencontre."""
        return list(self._passive.values())

    def courses_summary(self) -> list[dict]:
        """Résumé des courses touchées, dans l'ordre où elles ont été rencontrées
        (Python 3.7+ : ordre d'insertion du dict).

        Alimente le SSE `done` : le front en tire des liens « Voir les
        résultats » (#135). Ordre stable → boutons stables entre deux imports.
        """
        return [
            {
                "id": c.id, "name": c.name,
                "event_type": c.event_type, "is_relay": bool(c.is_relay),
            }
            for c in self._courses.values()
        ]

    def _index_course(self, course_id: int) -> None:
        """Charge et indexe une fois les participations de la course (une requête)."""
        if course_id in self._by_bib:
            return
        rows = participation_repository.list_for_course(self.db, course_id)
        by_bib: dict[str, Participation] = {}
        without: dict[str | None, list[Participation]] = {}
        for row in rows:
            if row.bib_number:
                by_bib[row.bib_number] = row
            else:
                without.setdefault(_stored_source_key(row), []).append(row)
        self._by_bib[course_id] = by_bib
        # Relais attribués sans dossard (#894) : appariés par nom d'équipe, la
        # fiche de l'équipe ayant disparu au profit des équipiers.
        teams: dict[str, list[Participation]] = {}
        for row in rows:
            if not row.bib_number and row.teammate_links and row.team_name:
                teams.setdefault(_team_key(row.team_name), []).append(row)
        # Plusieurs relais composés sous le même nom : on ne devine pas lequel
        # correspond à une ligne publiée, chacune consomme une place sans rien
        # mettre à jour (même règle que le multiset sans dossard).
        self._teams_without_bib[course_id] = {
            key: equipes if len(equipes) == 1 else [None] * len(equipes)
            for key, equipes in teams.items()
        }
        self._present_ids[course_id] = {row.athlete_id for row in rows} | {
            link.athlete_id for row in rows for link in row.teammate_links
        }
        self._reserved_keys[course_id] = set()
        self._added_bibs[course_id] = set()
        self._without_bib[course_id] = without
        self._credits[course_id] = {key: len(rs) for key, rs in without.items()}
        self._updated_single[course_id] = set()
        # `finalize()` réutilise cette liste (#706) au lieu d'un second
        # `list_for_course` : les créations de ce scrape s'y ajoutent au fil de
        # `_resolve_pending`, les mises à jour mutent les objets déjà dedans.
        self._participations[course_id] = list(rows)
        bibs_by_athlete: dict[int, set[str]] = {}
        for row in rows:
            if row.bib_number:
                bibs_by_athlete.setdefault(row.athlete_id, set()).add(row.bib_number)
        self._bibs_by_athlete[course_id] = bibs_by_athlete
        self._bib_keys[course_id] = {}

    def _upsert(self, existing: Participation, scraped: ScrapedResult) -> None:
        """Fusionne prudemment une ligne appariée. Compte `updated` ou `skipped`."""
        fields = _participation_fields(
            scraped, athlete_id=existing.athlete_id, course_id=existing.course_id
        )
        changes = _merge_fields(existing, fields)
        changes.update(_non_finisher_overrides(existing, scraped, fields))
        status = _resolve_status(existing, scraped, changes)
        if status != existing.status:
            changes["status"] = status
        # La clé source suit la ligne sans faire compter un résultat « mis à jour ».
        source_key = changes.pop("source_identity_key", None)
        if changes:
            self.updated += 1
        else:
            self.skipped += 1
        if source_key is not None:
            changes["source_identity_key"] = source_key
        if changes:
            participation_repository.update(self.db, existing, **changes)

    def _note_passive(self, course: Course, source: CourseSource) -> None:
        """Retient une source passive **une fois**, et rédige le message qui la nomme.

        Le message dit trois choses parce qu'il en faut trois pour être
        actionnable : l'épreuve qui a absorbé l'URL, la raison pour laquelle le
        classement affiché ne change pas, et qui peut décider l'inverse (#285).
        """
        if source.id in self._passive:
            return
        self._passive[source.id] = PassiveSource(
            url=source.url,
            course_name=course.name,
            message=(
                f"Cette URL est enregistrée comme source secondaire de "
                f"« {course.name} », dont les résultats affichés viennent d'un autre "
                f"chronométreur. Un administrateur peut la rendre principale."
            ),
        )

    def add(self, scraped: ScrapedResult) -> None:
        # Jamais de résolution sur une identité vide (`-`, clé normalisée vide,
        # #907) ni sur un nom masqué constant (« Anonymous », « XXX XXX », #897) :
        # toutes ces lignes, épreuves et événements confondus, fusionnaient sur
        # une seule fiche.
        published = _published_name(scraped)
        nameless = (
            is_masked_name(published)
            or athlete_identity_keys(scraped.athlete_name, scraped.athlete_firstname)[0] is None
        )
        opposed = not nameless and self._is_opposed(scraped)
        if (nameless or opposed) and not scraped.bib_number:
            logger.warning(
                "Row with a masked or empty name and no bib skipped: %s (%s)",
                scraped.event_name, scraped.source_url or self.event_url,
            )
            self.skipped += 1
            return
        cache_key = (
            scraped.provider,
            scraped.source_url or self.event_url,
            scraped.event_name,
            scraped.event_date,
            scraped.event_type,
            scraped.is_relay,
        )
        absorbed = self._absorbed.get(cache_key)
        if absorbed is None:
            absorbed = self._absorbed[cache_key] = mapping.is_absorbed(
                self.db, scraped, self.event_url
            )
            if absorbed:
                logger.info(
                    "Rows of a merged course ignored: %s (%s)",
                    scraped.event_name, scraped.source_url or self.event_url,
                )
        if absorbed:
            # Ni recréée, ni versée dans la cible (#983) : ni course résolue, ni
            # source rattachée, donc aucun message de source passive.
            self.skipped += 1
            return
        resolution = self._course_resolutions.get(cache_key)
        if resolution is None:
            resolution = self._resolve_locked_course(scraped)
            self._course_resolutions[cache_key] = resolution
        course = resolution.course
        if resolution.passive_source is not None:
            self._note_passive(course, resolution.passive_source)
        if course.id not in self._courses:
            # Constat de la machine, réécrit à chaque passage (#993).
            course.ranked_by_laps = scraped.ranked_by_laps
        self._courses[course.id] = course
        self._excluded_ranks[course.id] |= scraped.excluded_ranks
        self._index_course(course.id)
        if nameless or opposed:
            # Le dossard est unique sur l'épreuve : l'identité se retrouve au rescrape.
            scraped = replace(
                scraped, athlete_name=f"Anonyme {course.id}-{scraped.bib_number}",
                athlete_firstname="",
            )
        if opposed:
            # Opposition (#334) : rien de ce qui désigne la personne n'est gardé, rangs et temps si.
            # Un relais qui la compte reste entier mais anonyme : son libellé la nomme, et le
            # découper ferait renaître ce libellé en fiche d'équipe dès qu'un découpage est refusé.
            scraped = replace(scraped, club="", category="", raw_data={}, team_name="")
        bib = scraped.bib_number or None

        if bib is not None:
            added = self._added_bibs[course.id]
            if bib in added:
                # La source se contredit dans ce scrape : deux lignes, même
                # dossard. La 2e est perdue — anomalie de fiabilité.
                self.skipped += 1
                self._duplicate_bibs[course.id] += 1
                return
            self._bib_keys[course.id][bib] = _identity_key(scraped)
            existing = self._by_bib[course.id].get(bib)
            if existing is not None:
                added.add(bib)
                if existing.teammate_links or existing.athlete_locked:
                    # Relais attribué à ses équipiers (#894), ou fiche choisie par
                    # un admin (#896) : l'identité scrapée n'est ni résolue ni
                    # réconciliée, seules les valeurs suivent.
                    self._upsert(existing, scraped)
                    return
                teammates = _proposed_teammates(scraped)
                if teammates is not None:
                    # Relais importé avant #895 : découpé au lieu d'être réconcilié.
                    # La garde #66 suit la ligne, pour le cas où le découpage
                    # serait refusé à la résolution (FR-010).
                    self._enqueue(
                        course.id, scraped, bib=bib, participation=existing, teammates=teammates,
                        reconcile_blocked=self._reconcile_blocked(scraped, existing),
                    )
                    return
                # Deux axes indépendants sur une ligne appariée : l'identité
                # (`athlete_id`, #66) puis les valeurs (#68). La réconciliation
                # ne touche jamais aux valeurs, `_upsert` jamais à `athlete_id` —
                # les deux se rejouent dans `_resolve_pending`, une fois
                # l'athlète connu (#706, résolution par lot).
                if self._reconcile_blocked(scraped, existing):
                    # « BERGE | LOLA » → « LOLA BERGE |  » : refusé *avant*
                    # toute résolution, sinon une identité `(nom, "")` neuve
                    # serait mise en attente et créerait une fiche orpheline
                    # que le chemin web/SSE ne nettoie jamais (#66) — la
                    # garde doit trancher ici, pas après coup dans le lot.
                    self._upsert(existing, scraped)
                else:
                    self._enqueue(course.id, scraped, bib=bib, participation=existing)
                return
            # Dossard neuf : réservé tout de suite, sinon deux lignes neuves
            # du même scrape avec le même dossard passeraient toutes les deux
            # ce test (la résolution est différée, `_by_bib` ne les connaît
            # pas encore) et heurteraient `uq_participation_bib` à la création.
            added.add(bib)
        elif scraped.is_relay or course.is_relay:
            # `course.is_relay` : l'épreuve peut avoir été marquée relais à la
            # main, et `set_teammates` compose alors ses résultats.
            equipes = self._teams_without_bib[course.id].get(_team_key(_published_name(scraped)))
            if equipes:
                equipe = equipes.pop()
                if equipe is not None:
                    self._upsert(equipe, scraped)
                else:
                    self.skipped += 1
                return

        if not bib:
            locked = self._locked_without_bib(course.id, _source_key(scraped))
            if locked is not None:
                self._upsert(locked, scraped)
                return
        self._enqueue(
            course.id, scraped, bib=bib, participation=None,
            teammates=_proposed_teammates(scraped),
        )

    def _is_opposed(self, scraped: ScrapedResult) -> bool:
        """La ligne désigne une personne opposée (#334) : elle-même, ou l'un des équipiers
        qu'un libellé de relais nomme."""
        if not self._opposed:
            return False
        if identity_hash(scraped.athlete_name, scraped.athlete_firstname) in self._opposed:
            return True
        return any(identity_hash(*pair) in self._opposed for pair in _proposed_teammates(scraped) or ())

    def _enqueue(
        self, course_id: int, scraped: ScrapedResult, *, bib: str | None,
        participation: Participation | None,
        teammates: tuple[tuple[str, str], ...] | None = None,
        reconcile_blocked: bool = False,
    ) -> None:
        """Met une ligne en attente de résolution d'athlète (#706) au lieu de
        la résoudre immédiatement. Déclenche le lot dès que la tranche est
        pleine — le reliquat de chaque course se résout à `finalize()`."""
        item = _PendingResolution(
            scraped=scraped, bib=bib, participation=participation, teammates=teammates,
            reconcile_blocked=reconcile_blocked,
        )
        if teammates is not None:
            self._pending_splits.setdefault(course_id, []).append(item)
            return
        pending = self._pending.setdefault(course_id, [])
        pending.append(item)
        if len(pending) >= _TRANCHE_SIZE:
            self._resolve_pending(course_id)

    def _resolve_pending(self, course_id: int) -> None:
        """Résout par lot toutes les lignes en attente d'une course (#706).

        Un aller-retour DB pour retrouver les athlètes déjà connus
        (`get_by_identity_keys_batch`), un pour le repli d'identité des lignes
        restées sans fiche (`find_fallback_matches`, #908), un pour créer les manquants
        (`create_batch`, dédupliqué par identité — deux lignes du même scrape
        pour un même athlète neuf ne créent qu'une fiche), un seul pour les
        participations neuves. Rejoue ensuite, ligne par ligne mais sans
        requête, exactement la logique de `add`/`_reconcile` d'origine.
        Une ligne d'un autre club qu'une fiche de membre part sur un homonyme
        (#1209, `_athlete_for_club`).
        """
        pending = self._pending.pop(course_id, [])
        if not pending:
            return

        # Une ligne source inchangée garde sa fiche : ni recherche ni repli pour elle.
        kept = [self._kept_record(course_id, item) if item.teammates is None else None for item in pending]
        pairs = [
            (item.scraped.athlete_name, item.scraped.athlete_firstname)
            for item, record in zip(pending, kept, strict=True) if record is None
        ]
        teammate_pairs = [pair for item in pending for pair in item.teammates or ()]
        pairs += teammate_pairs + [pair[::-1] for pair in teammate_pairs]
        found = athlete_repository.get_by_identity_keys_batch(self.db, [_pair_key(pair) for pair in pairs])
        unresolved = [
            key for key in dict.fromkeys(
                _identity_key(item.scraped)
                for item, record in zip(pending, kept, strict=True)
                if item.teammates is None and record is None
            )
            if key not in found
        ]
        # Une graphie absorbée par une fusion admin est une variante de la fiche
        # conservée (#908) : elle passe avant tout repli, et sous la même garde
        # (deux dossards d'une épreuve sont deux personnes, FR-008). Les équipiers
        # d'un relais la suivent aussi, dans les deux sens de lecture.
        teammate_keys = [
            key for pair in teammate_pairs for key in (_pair_key(pair), _pair_key(pair[::-1])) if key not in found
        ]
        found.update(athlete_alias_repository.get_by_keys_batch(self.db, teammate_keys))
        aliased = athlete_alias_repository.get_by_keys_batch(self.db, unresolved)
        unresolved = [key for key in unresolved if key not in aliased]
        fallback, ambiguous = athlete_repository.find_fallback_matches(self.db, unresolved)
        found.update(self._safe_fallbacks(course_id, pending, found, {**aliased, **fallback}))
        pending = [
            replace(item, teammates=_oriented_teammates(item.teammates, found))
            if item.teammates else item
            for item in pending
        ]
        decisions = self._split_decisions(course_id, pending, found)

        to_create: dict[IdentityKey, dict] = {}
        creation_order: list[IdentityKey] = []
        for item, teammates, record in zip(pending, decisions, kept, strict=True):
            if teammates is None and (item.reconcile_blocked or record is not None):
                continue
            if teammates is None:
                candidates = [
                    (_identity_key(item.scraped), mapping.athlete_creation_fields(item.scraped))
                ]
            else:
                # Un équipier ne reçoit ni le club ni le genre de l'équipe (#895) ;
                # la fiche au nom de l'équipe n'est jamais créée.
                candidates = [
                    (_pair_key(pair), {"nom": pair[0], "prenom": pair[1], "gender": "",
                                       "birth_date": None, "club": None})
                    for pair in teammates
                ]
            for key, fields in candidates:
                if key in found or key in to_create:
                    continue
                to_create[key] = fields
                creation_order.append(key)
        if creation_order:
            created_athletes, inserted_ids = athlete_repository.create_batch(
                self.db, [to_create[key] for key in creation_order]
            )
            found.update(zip(creation_order, created_athletes, strict=True))
            # Une fiche rendue sans avoir été insérée vient d'un import concurrent :
            # s'y rattacher est une fusion, pas une création (#981).
            created_keys = {
                key for key, athlete in zip(creation_order, created_athletes, strict=True)
                if athlete.id in inserted_ids
            }
        else:
            created_keys = set()
        self.ambiguous_identities.extend(
            {"course_id": course_id, "athlete_id": found[key].id, "candidate_ids": candidate_ids}
            for key, candidate_ids in ambiguous.items()
            if key in found
        )

        # Une seule requête par tranche, bornée aux fiches dont le club changerait.
        course_date = self._courses[course_id].event_date
        member_clubs, club_homonyms = self._club_routing(course_id, pending, decisions, kept, found)
        club_changes = {
            athlete.id
            for item, teammates, record in zip(pending, decisions, kept, strict=True)
            if teammates is None and not item.reconcile_blocked and item.scraped.club
            for athlete in [record or found[_identity_key(item.scraped)]]
            if self._club_of(athlete) != item.scraped.club and not athlete.club_locked
        }
        # Un homonyme repris par le signal de club suit la même garde de date (#965).
        club_changes.update(
            homonym.id for listed in club_homonyms.values() for homonym, _ in listed if not homonym.club_locked
        )
        club_changes.update(homonym.id for homonym in self._club_homonyms.values() if not homonym.club_locked)
        latest_clubs = athlete_repository.latest_club_dates(self.db, list(club_changes))

        creation_consumed: set[IdentityKey] = set()
        new_participation_fields: list[dict] = []
        new_participation_items: list[_PendingResolution] = []
        team_athletes: list[int] = []

        for item, teammates, record in zip(pending, decisions, kept, strict=True):
            if teammates is not None:
                self._apply_split(
                    course_id, item, [found[_pair_key(pair)] for pair in teammates],
                    team=found.get(_identity_key(item.scraped)),
                    new_fields=new_participation_fields, new_items=new_participation_items,
                    team_athletes=team_athletes,
                )
                continue
            if item.reconcile_blocked:
                self._upsert(item.participation, item.scraped)
                continue
            key = _identity_key(item.scraped)
            athlete = resolved = record or found[key]
            if record is None and item.participation is None and athlete.id in member_clubs:
                athlete = self._athlete_for_club(
                    course_id, item, athlete, member_clubs[athlete.id], club_homonyms.get(key, [])
                )
            if record is None and item.bib is not None:
                athlete = self._athlete_for_bib(course_id, item, athlete)
            created_for_bib = athlete is not resolved and athlete.id in self._created_for_bibs
            self._present_ids[course_id].add(athlete.id)
            club = item.scraped.club or None
            if (
                club and self._club_of(athlete) != club and not athlete.club_locked
                and athlete_repository.club_is_current(course_date, latest_clubs.get(athlete.id))
            ):
                # Même règle que la branche « existant » de
                # `athlete_repository.resolve` — sans effet sur la ligne qui
                # vient de créer `athlete` (son club est déjà le sien).
                self._defer_update(athlete, club=club)
            gender = normalize_gender(item.scraped.gender)
            if gender and not self._gender_of(athlete):
                self._defer_update(athlete, gender=gender)

            is_creator = created_for_bib or (
                record is None and key in created_keys and key not in creation_consumed
            )
            if is_creator:
                creation_consumed.add(key)

            if item.participation is not None:
                self._reconcile_resolved(
                    item.scraped, item.participation, athlete, cree=is_creator
                )
                self._upsert(item.participation, item.scraped)
                continue

            if item.bib is None:
                source_key = _source_key(item.scraped)
                existing = self._match_without_bib(course_id, source_key)
                if existing is not None:
                    self._upsert(existing, item.scraped)
                    continue
                if self._credits[course_id].get(source_key, 0) > 0:
                    self._credits[course_id][source_key] -= 1
                    self.skipped += 1
                    continue

            new_participation_fields.append(
                _participation_fields(item.scraped, athlete_id=athlete.id, course_id=course_id)
            )
            new_participation_items.append(item)

        if new_participation_fields:
            created_participations = participation_repository.create_batch(
                self.db, new_participation_fields
            )
            self._participations[course_id].extend(created_participations)
            for item, participation in zip(
                new_participation_items, created_participations, strict=True
            ):
                # `_added_bibs` est déjà à jour depuis `add` (réservé dès
                # l'enfilement, cf. commentaire associé) — seul `_by_bib` a
                # besoin de l'objet créé, indisponible avant la création.
                if item.bib is not None:
                    self._by_bib[course_id][item.bib] = participation
                self.imported += 1
        if team_athletes:
            # `autoflush` est coupé : sans ce flush, la purge lirait encore
            # l'ancien porteur d'un résultat repris sans autre changement.
            self.db.flush()
            athlete_repository.delete_orphans_among(self.db, team_athletes)

    def _athlete_for_bib(self, course_id: int, item: _PendingResolution, athlete: Athlete) -> Athlete:
        """La fiche d'un dossard : celle de son identité, sauf si un autre dossard
        de cette épreuve individuelle court déjà sous ce nom sur cette fiche (#967).

        Un coureur ne prend pas deux dossards sur une course individuelle : le
        second reçoit une fiche d'homonyme distinguée, que l'import ne visera plus
        par l'identité. Vaut pour un dossard neuf comme pour une correction de nom
        de la source (FR-008). Une fiche trouvée par repli (nom inversé ou
        concaténé) n'a pas la clé de la ligne : c'est alors la fiche principale de
        cette clé qui est créée, jamais un homonyme sans principale.
        """
        if not self._races_twice(course_id, item, athlete):
            self._bibs_by_athlete[course_id].setdefault(athlete.id, set()).add(item.bib)
            return athlete
        fields = mapping.athlete_creation_fields(item.scraped)
        if (athlete.last_name_key, athlete.first_name_key) != _identity_key(item.scraped):
            [principal], inserted = athlete_repository.create_batch(self.db, [fields])
            self._created_for_bibs.update(inserted)
            if not self._races_twice(course_id, item, principal):
                self._bibs_by_athlete[course_id].setdefault(principal.id, set()).add(item.bib)
                return principal
            athlete = principal
        homonym = athlete_repository.create_homonym(self.db, fields)
        self._created_for_bibs.add(homonym.id)
        self._bibs_by_athlete[course_id][homonym.id] = {item.bib}
        self.homonyms_created.append({
            "course_id": course_id, "bib": item.bib, "athlete_id": homonym.id, "homonym_of": athlete.id,
        })
        return homonym

    def _club_keys(self, athlete_ids: set[int]) -> dict[int, set[str]]:
        """Clubs d'une fiche : ceux de ses résultats et ceux qu'un admin a confirmés."""
        labels = athlete_repository.club_labels_by_athlete(self.db, athlete_ids)
        known = athlete_known_club_repository.keys_by_athlete(self.db, athlete_ids)
        return {
            athlete_id: {
                canonical_club_key(label, self._club_aliases) for label in labels.get(athlete_id, {})
            } | known.get(athlete_id, set())
            for athlete_id in athlete_ids
        }

    def _club_routable(self, course_id: int, item: _PendingResolution) -> bool:
        """Vrai si le club de la ligne peut l'envoyer sur un homonyme (#1209). Une
        ligne sans dossard dont la clé source a déjà des résultats sur l'épreuve ne
        fait que mettre à jour ou sauter l'un d'eux : l'homonyme resterait vide."""
        if self._courses[course_id].is_relay or item.scraped.is_relay or not is_significant_club(item.scraped.club):
            return False
        return item.bib is not None or not self._without_bib[course_id].get(_source_key(item.scraped))

    def _club_routing(
        self, course_id: int, pending: list[_PendingResolution], decisions: list,
        kept: list[Athlete | None], found: dict[IdentityKey, Athlete],
    ) -> tuple[dict[int, set[str]], dict[IdentityKey, list[tuple[Athlete, set[str]]]]]:
        """Ce que `_athlete_for_club` lit, en quelques requêtes par tranche (#1209) :
        les clubs des fiches de membre qu'une ligne d'un autre club pourrait viser,
        puis les homonymes de ces lignes avec leurs clubs."""
        # La fiche de membre se juge sur l'état d'avant l'import : les verdicts du
        # club ne se recalculent qu'en `finalize`. Une fiche qui devient membre par
        # cet import même est rattrapée par la revue `multi_club`.
        candidates = [
            (_identity_key(item.scraped), canonical_club_key(item.scraped.club, self._club_aliases))
            for item, teammates, record in zip(pending, decisions, kept, strict=True)
            if teammates is None and record is None and item.participation is None
            and not item.reconcile_blocked and self._club_routable(course_id, item)
        ]
        principals = {found[key].id for key, _ in candidates}
        if not principals:
            return {}, {}
        member_clubs = self._club_keys(athlete_repository.member_record_ids(self.db, principals))
        foreign = {
            key for key, club_key in candidates
            if found[key].id in member_clubs and club_key not in member_clubs[found[key].id]
            and (key, club_key) not in self._club_homonyms
        }
        homonyms = athlete_repository.homonyms_of(self.db, foreign)
        clubs = self._club_keys({homonym.id for listed in homonyms.values() for homonym in listed})
        return member_clubs, {
            key: [(homonym, clubs[homonym.id]) for homonym in listed] for key, listed in homonyms.items()
        }

    def _athlete_for_club(
        self, course_id: int, item: _PendingResolution, athlete: Athlete, known_keys: set[str],
        homonyms: list[tuple[Athlete, set[str]]],
    ) -> Athlete:
        """La fiche d'une ligne publiée sous un autre club que ceux d'une fiche de
        membre (#1209) : l'homonyme de même nom qui porte déjà ce club, sinon un
        nouvel homonyme, jugé distinct d'office pour que la reprise ne le refusionne
        pas. Une fiche trouvée par variante ou par repli n'a pas la clé de la
        ligne : rien n'est décidé sur elle. Club vide, ville ou libellé du club :
        la ligne reste sur la fiche de membre."""
        if not self._club_routable(course_id, item):
            return athlete
        club_key = canonical_club_key(item.scraped.club, self._club_aliases)
        identity = _identity_key(item.scraped)
        if club_key in known_keys or (athlete.last_name_key, athlete.first_name_key) != identity:
            return athlete
        routed = self._club_homonyms.get((identity, club_key))
        if routed is None:
            routed = next((homonym for homonym, clubs in homonyms if club_key in clubs), None)
        if routed is None:
            routed = athlete_repository.create_homonym(self.db, mapping.athlete_creation_fields(item.scraped))
            ignored_athlete_pair_repository.create(
                self.db, athlete_id_a=athlete.id, athlete_id_b=routed.id, user_id=None
            )
            self._created_for_bibs.add(routed.id)
            self.homonyms_created.append({
                "course_id": course_id, "bib": item.bib, "athlete_id": routed.id, "homonym_of": athlete.id,
            })
        self._club_homonyms[(identity, club_key)] = routed
        return routed

    def _races_twice(self, course_id: int, item: _PendingResolution, athlete: Athlete) -> bool:
        """Vrai si `athlete` porte, sur cette épreuve individuelle, un autre dossard
        que ce scrape publie sous la même identité que la ligne. Un dossard absent
        du scrape (périmé) ou passé à un autre nom ne compte pas. Jamais sur un
        relais, où une même personne peut figurer plusieurs fois."""
        if self._courses[course_id].is_relay or item.scraped.is_relay:
            return False
        key = _identity_key(item.scraped)
        published = self._bib_keys[course_id]
        return any(
            bib != item.bib and published.get(bib) == key
            for bib in self._bibs_by_athlete[course_id].get(athlete.id, ())
        )

    def _kept_record(self, course_id: int, item: _PendingResolution) -> Athlete | None:
        """La fiche qu'une ligne source inchangée garde, sans résolution (#896).

        Même clé source qu'au dernier passage : la ligne reste sur la fiche de sa
        participation, même renommée, datée ou distinguée par un admin depuis.
        La résoudre recréerait l'ancienne graphie en fiche vide.
        """
        source_key = _source_key(item.scraped)
        if item.participation is not None:
            return item.participation.athlete if _stored_source_key(item.participation) == source_key else None
        if item.bib is not None:
            return None
        # Sans dossard, seulement si la ligne sera bien appariée ou comptée sur
        # une seule fiche : une ligne de plus que la base, ou une clé dont une
        # ligne a été réattribuée par un admin, se résout comme une ligne neuve,
        # sans quoi elle irait à la fiche choisie par l'admin.
        rows = self._without_bib[course_id].get(source_key, [])
        if (
            self._credits[course_id].get(source_key, 0) <= 0
            or len({row.athlete_id for row in rows}) != 1
            or any(row.athlete_locked or row.teammate_links for row in rows)
        ):
            return None
        return rows[0].athlete

    def _safe_fallbacks(
        self, course_id: int, pending: list[_PendingResolution],
        direct: dict[IdentityKey, Athlete], fallback: dict[IdentityKey, Athlete],
    ) -> dict[IdentityKey, Athlete]:
        """Les rattachements par repli qui ne fusionnent pas deux personnes (#908).

        « THOMAS Martin » (dossard 1) et « MARTIN Thomas » (dossard 2) sur une
        même épreuve sont deux coureurs : un repli est écarté si sa fiche porte,
        sur l'épreuve, un dossard que ses propres lignes n'ont pas (participation
        connue, ou ligne de ce lot résolue en direct), ou si une autre clé y
        aboutit aussi. Comparer les dossards, et non la seule présence, garde le
        rescrape : la participation déjà rattachée porte celui de la ligne.
        """
        if not fallback:
            return fallback
        bibs_by_key: dict[IdentityKey, set[str | None]] = {}
        for item in pending:
            if item.teammates is None:
                bibs_by_key.setdefault(_identity_key(item.scraped), set()).add(item.bib)
        claimed: dict[int, set[str | None]] = {}
        for key, athlete in direct.items():
            claimed.setdefault(athlete.id, set()).update(bibs_by_key.get(key, ()))
        for participation in self._participations[course_id]:
            claimed.setdefault(participation.athlete_id, set()).add(participation.bib_number or None)
        targets = Counter(athlete.id for athlete in fallback.values())
        return {
            key: athlete for key, athlete in fallback.items()
            if targets[athlete.id] == 1 and claimed.get(athlete.id, set()) <= bibs_by_key.get(key, set())
        }

    def _split_decisions(
        self, course_id: int, pending: list[_PendingResolution],
        found: dict[IdentityKey, Athlete],
    ) -> list[tuple[tuple[str, str], ...] | None]:
        """Équipiers retenus par ligne, `None` si la ligne n'est pas découpée (#895).

        FR-010 : un équipier déjà présent sur la course (en base, ou réservé par
        une ligne de ce scrape, découpée ou non) laisse la ligne entière, qui suit
        alors le chemin d'avant #895.
        """
        present_ids = self._present_ids[course_id]
        reserved = self._reserved_keys[course_id]
        reserved.update(_identity_key(item.scraped) for item in pending if item.teammates is None)
        claimed_teams: set[str | None] = set()
        decisions = []
        for item in pending:
            teammates = item.teammates
            if teammates is not None:
                keys = [_pair_key(pair) for pair in teammates]
                ids = {found[key].id for key in keys if key in found}
                if (
                    len(set(keys)) != len(keys)
                    or reserved.intersection(keys) or present_ids & ids
                    or not self._bibless_team_claimable(course_id, item, found, claimed_teams)
                ):
                    teammates = None
                    reserved.add(_identity_key(item.scraped))
                else:
                    reserved.update(keys)
                    present_ids.update(ids)
            decisions.append(teammates)
        return decisions

    def _bibless_team_claimable(
        self, course_id: int, item: _PendingResolution,
        found: dict[IdentityKey, Athlete], claimed_teams: set[str | None],
    ) -> bool:
        """Faux si la fiche d'équipe d'une ligne sans dossard a des lignes sur la
        course sans qu'une seule puisse être reprise : découper créerait un
        résultat en double, là où le chemin d'avant #895 les compte (crédits).
        """
        if item.bib is not None or item.participation is not None:
            return True
        source_key = _source_key(item.scraped)
        rows = self._without_bib[course_id].get(source_key, [])
        if not rows:
            return True
        if len(rows) != 1 or source_key in self._updated_single[course_id] or source_key in claimed_teams:
            return False
        claimed_teams.add(source_key)
        return True

    def _apply_split(
        self, course_id: int, item: _PendingResolution, teammates: list[Athlete], *,
        team: Athlete | None, new_fields: list[dict], new_items: list[_PendingResolution],
        team_athletes: list[int],
    ) -> None:
        """Rattache une ligne de relais découpée à ses équipiers (#895).

        Un résultat existant sans composition (importé avant #895, par dossard ou
        par sa fiche d'équipe) est repris sur place et sa fiche d'équipe devient
        candidate à la purge ; sinon la participation est créée composée.
        """
        scraped = replace(item.scraped, team_name=_published_name(item.scraped))
        ids = [athlete.id for athlete in teammates]
        self._present_ids[course_id].update(ids)
        existing = item.participation
        if existing is None and item.bib is None:
            existing = self._match_without_bib(course_id, _source_key(item.scraped))
        if existing is None:
            fields = _participation_fields(scraped, athlete_id=ids[0], course_id=course_id)
            fields["teammate_ids"] = ids
            new_fields.append(fields)
            new_items.append(item)
            return
        team_athletes.append(existing.athlete_id)
        participation_repository.replace_teammates(self.db, existing, ids)
        existing.athlete = teammates[0]
        self._upsert(existing, scraped)

    def _reconcile_blocked(self, scraped: ScrapedResult, participation: Participation) -> bool:
        """Vrai si la réconciliation de cette ligne doit être refusée sans
        même résoudre d'athlète — jamais une correction qui viderait le
        prénom : « BERGE | LOLA » → « LOLA BERGE |  » créerait une identité
        `(nom, "")` neuve, orpheline, que le chemin web/SSE ne nettoie jamais
        (#66). Vérifié à l'enfilement (`add`), avant toute mise en attente de
        résolution — trancher après coup, une fois l'identité déjà mise en
        lot, serait trop tard pour éviter la création."""
        ancien = participation.athlete
        return not (scraped.athlete_firstname or "").strip() and (ancien.prenom or "").strip()

    def _reconcile_resolved(
        self, scraped: ScrapedResult, participation: Participation, athlete: Athlete,
        *, cree: bool,
    ) -> None:
        """Réassigne l'athlète d'une participation existante si sa clé source a
        changé (le chronométreur a corrigé le nom, #896). `athlete`/`cree` sont déjà connus (résolus par lot dans
        `_resolve_pending`, `_reconcile_blocked` déjà écarté à l'enfilement) —
        c'est la seule différence avec l'ancien `_reconcile`, qui résolvait
        lui-même l'athlète par une requête. Ne touche QUE `athlete_id` (via la
        relation, pour un déplacement propre entre fiches sans déclencher le
        cascade delete-orphan) : les valeurs de la ligne relèvent d'`_upsert`,
        appelé juste après. Compte « réconciliée » quand l'athlète change —
        jamais `skipped`, qui reste l'affaire d'`_upsert` pour ne pas compter
        deux fois la même ligne.
        """
        if athlete.id == participation.athlete_id:
            return
        # Même ligne source qu'au dernier passage : le chronométreur n'a rien
        # changé, la fiche actuelle (renommée, datée ou homonyme distingué par un
        # admin) reste la bonne (#896, #900).
        if _stored_source_key(participation) == _source_key(scraped):
            return
        reassignment = Reassignment(
            ancien=_identite(participation.athlete), nouveau=_identite(athlete), fusion=not cree
        )
        self._previous_athlete_ids.add(participation.athlete_id)
        participation.athlete = athlete
        if participation.bib_number:
            self._bibs_by_athlete[participation.course_id].setdefault(athlete.id, set()).add(
                participation.bib_number
            )
        self.reconciled += 1
        self.reassignments.append(reassignment)

    def _match_without_bib(self, course_id: int, source_key: str | None) -> Participation | None:
        """Ligne sans dossard à mettre à jour : seulement si la clé source n'a
        qu'**une** participation sur la course, et pas déjà mise à jour dans ce scrape.

        Deux occurrences ou plus : on ne devine pas quelle ligne source correspond
        à quelle ligne en base, on conserve le skip multiset (cf. `add`).
        """
        rows = self._without_bib[course_id].get(source_key, [])
        if len(rows) != 1 or source_key in self._updated_single[course_id]:
            return None
        self._updated_single[course_id].add(source_key)
        self._credits[course_id][source_key] -= 1
        return rows[0]

    def _locked_without_bib(self, course_id: int, source_key: str | None) -> Participation | None:
        """La ligne sans dossard réattribuée par un admin que cette clé source
        désigne, appariée **avant** toute résolution : la fiche d'origine, purgée
        à la réattribution, n'est pas recréée (#896)."""
        rows = self._without_bib[course_id].get(source_key, [])
        if len(rows) != 1 or not rows[0].athlete_locked:
            return None
        return self._match_without_bib(course_id, source_key)

    def _resolve_locked_course(self, scraped: ScrapedResult) -> mapping.CourseResolution:
        """Résout l'épreuve, puis la verrouille (#982).

        Le verrou attend la fin d'un geste admin sur l'épreuve plutôt que
        d'écrire sous lui ; le geste, lui, reçoit un 409 tant que l'import la
        tient. Si ce geste l'a supprimée pendant l'attente, la ligne résolue
        n'existe plus : on la résout de nouveau, ce qui la recrée.
        """
        resolution = mapping.get_or_create_course(self.db, scraped, self.event_url)
        if resolution.course.id in self._courses:
            return resolution
        lock_repository.lock_course(self.db, resolution.course.id)
        if course_repository.get_fresh(self.db, resolution.course.id) is None:
            self.db.expunge(resolution.course)
            resolution = mapping.get_or_create_course(self.db, scraped, self.event_url)
            lock_repository.lock_course(self.db, resolution.course.id)
        return resolution

    def _defer_update(self, athlete: Athlete, **fields: str) -> None:
        """Retient un changement de club ou de genre, appliqué par `finalize` (#980).

        Écrits au fil des tranches, dans l'ordre du chronométreur, ces UPDATE
        partaient sur plusieurs flush : SQLAlchemy ne les trie par clé qu'à
        l'intérieur d'un flush, et deux imports concurrents prenaient les mêmes
        lignes dans des ordres croisés, jusqu'au deadlock (#771).
        """
        self._athlete_updates.setdefault(athlete.id, (athlete, {}))[1].update(fields)

    def _club_of(self, athlete: Athlete) -> str | None:
        pending = self._athlete_updates.get(athlete.id)
        return pending[1].get("club", athlete.club) if pending else athlete.club

    def _gender_of(self, athlete: Athlete) -> str:
        pending = self._athlete_updates.get(athlete.id)
        return pending[1].get("gender", athlete.gender) if pending else athlete.gender

    def finalize(self) -> None:
        # Reliquat de chaque course : ce qui n'a pas atteint une pleine
        # tranche pendant `add` se résout ici (#706).
        for course_id in list(self._pending.keys()):
            self._resolve_pending(course_id)
        for course_id, splits in self._pending_splits.items():
            self._pending[course_id] = splits
            self._resolve_pending(course_id)
        # Un second passage (lignes Challenge rendues au flux normal, #1008) ne
        # doit pas résoudre deux fois les mêmes découpages.
        self._pending_splits.clear()
        if self._athlete_updates:
            athlete_repository.apply_updates(
                self.db, [self._athlete_updates[aid] for aid in sorted(self._athlete_updates)]
            )
            self._athlete_updates.clear()
        # Verdict du club avant les compteurs : `recount` le lit (#1206). La
        # portée s'étend aux autres résultats des athlètes importés.
        tcn_count_repository.recompute_counts_for_tcn(
            self.db, course_ids=list(self._courses), athlete_ids=self._previous_athlete_ids
        )
        for course_id, course in self._courses.items():
            course_repository.touch_scraped_at(self.db, course)
            course_source_repository.touch_active_scraped_at(self.db, course_id)
            # Réutilise la liste déjà chargée par `_index_course` (#706), tenue à
            # jour par `_resolve_pending`, au lieu d'un second `list_for_course`.
            # Les compteurs, eux, se recalculent en base (#1099).
            rows = self._participations[course_id]
            report = quality.analyze(
                rows,
                duplicate_bibs=self._duplicate_bibs[course_id],
                excluded_ranks=self._excluded_ranks[course_id],
            )
            course_repository.set_quality(
                self.db,
                course,
                is_reliable_computed=report.is_reliable,
                quality_issues=report.anomalies,
            )
            course_repository.recount(self.db, course)


def _redate_heats(db: Session, results: list[ScrapedResult]) -> None:
    """Redate l'épreuve rapprochée par la règle R sur la date lue pour son heat (#972).

    `mapping.get_or_create_course` retrouve une épreuve Klikego par
    `(platform_event_id, heat_slug)` sans jamais réécrire sa date : sans ce
    rattrapage, un rescrape laissait les heats datés du premier jour de
    l'événement. Seule une date marquée `heat_dated` fait foi. Le repli sur la
    date d'événement (`--single-heat`, heat absent de l'index) ne réécrit rien,
    sans quoi il défairait la correction ; les deux façades Breizh Chrono, qui
    divergent sur la date (#289), n'y touchent pas non plus.

    Posée **avant** `_reclassify_heats` et `_renumber_relay_split_ranks`, qui
    cherchent l'épreuve à la date scrapée.
    """
    dated = {
        (scraped.provider, scraped.source_url): scraped.event_date
        for scraped in results
        if scraped.heat_dated and scraped.event_date and scraped.source_url
    }
    for (provider, url), event_date in dated.items():
        course = course_reconciliation.find_reconcilable_course(
            db, provider=provider, source_url=url
        )
        if course is not None:
            course_repository.redate(db, course, event_date)


def _reclassify_heats(db: Session, event_url: str, results: list[ScrapedResult]) -> None:
    """Aligne la classification des épreuves déjà en base sur ce scrape-ci (#294).

    Le verdict de `classify_event_type` bouge d'un scrape à l'autre — heuristique
    affinée, contexte de nom différent. L'identité étant
    `(name, event_date, event_type, is_relay)`, l'épreuve ne se retrouvait plus :
    une **seconde** `Course` naissait, et la première gardait ses résultats sous
    un sport devenu faux, indiscernable de la neuve à l'écran (Mesquer 2026, 498
    finishers classés swimrun alors que c'était un triathlon).

    **Un rattrapage de lot, et pas de ligne**, parce que le signal qui distingue
    une reclassification d'un second heat n'existe qu'au niveau du lot : une même
    URL publie légitimement N épreuves du **même nom**, à la **même date**, que
    seuls `event_type` et `is_relay` séparent — les six heats TimePulse sous
    `/epreuves/resultats/live/3232` (mesuré, cf.
    `services/course_duplicates._same_source_url`). Ligne à ligne, le second heat
    est indistinguable d'un premier heat reclassé, et le rattraper reviendrait à
    fondre deux classements réels en un. Le lot, lui, tranche : si ce scrape ne
    publie **qu'une** classification pour une clé, il n'y a pas deux heats à
    confondre.

    Rien n'est écrit quand l'URL scrapée n'est pas la source **active** de
    l'épreuve : c'est D2 (#303), la source active fait foi sur le nom, la date, et
    donc aussi sur le sport. Une passive n'alimente aucun affichage, elle ne
    classe rien.

    Le coût est d'**une lecture indexée par heat** sur le chemin nominal — celui
    où l'identité n'a pas bougé, et où il n'y a donc rien à reclasser. La jointure
    sur `course_sources` n'est payée que quand elle a bougé, c'est-à-dire presque
    jamais.
    """
    classifications: dict[tuple[str, str, object, bool], set[str]] = {}
    for scraped in results:
        # Même priorité que `mapping.get_or_create_course` : le fan-out Klikego
        # (#156) donne à chaque heat sa propre URL, et c'est elle qui porte la
        # source active de l'épreuve, pas l'URL d'événement soumise.
        url = scraped.source_url or event_url
        if not url:
            continue
        cle = (url, scraped.event_name, scraped.event_date, bool(scraped.is_relay))
        classifications.setdefault(cle, set()).add(scraped.event_type)

    for (url, name, event_date, is_relay), types in classifications.items():
        if len(types) != 1:
            continue
        event_type = next(iter(types))
        if course_repository.get_by_identity(db, name, event_date, event_type, is_relay):
            # L'identité visée est déjà en base : ou bien c'est l'épreuve elle-même
            # et rien n'a bougé, ou bien c'en est une autre et `uq_course_identity`
            # interdirait l'écriture de toute façon.
            continue
        course = course_repository.get_by_active_source(
            db, source_url=url, name=name, event_date=event_date, is_relay=is_relay
        )
        if course is not None:
            course_repository.reclassify(db, course, event_type)


CourseIdentity = tuple[str, object, str, bool]


def _reidentify_heats(db: Session, event_url: str, results: list[ScrapedResult]) -> None:
    """Met à jour en place l'épreuve que ce scrape publie sous une autre identité (#1204, #1197).

    Le rescrape de la MEP v0.8.0 a recréé 44 épreuves à côté des anciennes, même
    URL, mêmes dossards : Wiclax ne met plus l'année dans le nom (« Triathlon de
    Vertou 2025 - Triathlon S » → « Triathlon de Vertou - Triathlon S »). Et 28
    épreuves d'équipe autrefois solo ont reçu une jumelle relais, `is_relay`
    entrant dans l'identité depuis #963.

    Comme `_reclassify_heats`, un geste de lot : une URL publie légitimement
    plusieurs heats, et une ligne seule ne dit pas si son identité est neuve ou
    déplacée. Les **dossards** tranchent : une épreuve dont cette URL est la
    source active, absente de ce scrape, et dont la majorité des dossards est
    reprise par une identité neuve (et inversement), est la même épreuve. Un
    heat ajouté à la page, aux dossards distincts, reste une épreuve neuve ; deux
    candidates à égalité ne se tranchent pas, l'import crée alors l'épreuve comme
    avant et `/admin/doublons` la signale.

    Deux exclusions. Klikego et Breizh Chrono ont la règle R (#289), qui retrouve
    déjà l'épreuve sans regarder son identité, et dont les deux façades nomment
    différemment : les renommer ferait osciller le nom à chaque bascule. Et une
    épreuve dont un admin a corrigé l'identité (`course.update`) la garde.
    """
    published: dict[str, dict[CourseIdentity, set[str]]] = {}
    for scraped in results:
        url = scraped.source_url or event_url
        if (
            not url
            or not scraped.event_name
            or scraped.provider in course_reconciliation.RECONCILABLE_PROVIDERS
        ):
            continue
        identity = (
            course_repository.clean_name(scraped.event_name),
            scraped.event_date,
            scraped.event_type,
            bool(scraped.is_relay),
        )
        bibs = published.setdefault(url, {}).setdefault(identity, set())
        if scraped.bib_number:
            bibs.add(scraped.bib_number)

    for url, identities in published.items():
        missing = [
            identity
            for identity, bibs in identities.items()
            if bibs
            and course_repository.get_by_identity(db, *identity) is None
            and not absorbed_course_repository.is_absorbed(
                db, url=url, name=identity[0], event_date=identity[1],
                event_type=identity[2], is_relay=identity[3],
            )
        ]
        if not missing:
            continue
        orphans = [
            course
            for course in course_repository.list_by_source_url(db, url)
            if (course.name, course.event_date, course.event_type, course.is_relay) not in identities
        ]
        corrected = admin_action_log_repository.entity_ids_with_action(
            db, action="course.update", entity_ids=[c.id for c in orphans]
        )
        orphans = [course for course in orphans if course.id not in corrected]
        if not orphans:
            continue
        orphan_bibs = participation_repository.named_bibs_by_course(db, [c.id for c in orphans])
        for name, event_date, event_type, is_relay in missing:
            bibs = identities[(name, event_date, event_type, is_relay)]
            # La date reste hors du geste : seule une date lue par heat la réécrit
            # (`_redate_heats`, #972), un repli sur la date d'événement jamais.
            matches = [
                course
                for course in orphans
                if course.event_date == event_date
                and 2 * len(orphan_bibs[course.id] & bibs) > max(len(orphan_bibs[course.id]), len(bibs))
            ]
            if len(matches) != 1:
                continue
            (course,) = matches
            orphans.remove(course)
            logger.info(
                "Course %s re-identified by its source %s: %r -> %r (relay %s -> %s)",
                course.id, url, course.name, name, course.is_relay, is_relay,
            )
            course_repository.update_identity(
                db, course, name=name, event_date=event_date, event_type=event_type, is_relay=is_relay
            )


def _renumber_relay_split_ranks(db: Session, results: list[ScrapedResult]) -> None:
    """Renumérote `rank_overall` en 1..N quand la scission par `is_relay` a lieu (#672).

    L'identité `Course` (`name, event_date, event_type, is_relay`) scinde en
    deux épreuves une source qui n'en publie qu'une (solo + relais/duo mêlés
    dans un même « heat »). Le `rank_overall` scrapé porte alors le rang dans
    le **champ combiné** de la source — inchangé après la scission, le petit
    lot hérite d'un rang très écarté (ex. 597 pour 3 relayeurs), ce qui casse
    l'hypothèse de `services/quality.py::_rank_anomalies` (classement local
    1..N sans trou, cf. `ANOMALY_RANK_GAP`) et affiche un « trou » de
    centaines de rangs sur une fiche de 1 à 16 participants — déroutant côté
    site. Constaté sur ProLiveSport et Chronoplace, deux scrapers sans code
    partagé : la cause commune est l'identité `Course`, pas un fournisseur.

    Renuméroté ici, au point précis où le lot scrapé se répartit par
    `is_relay` — pas dans les scrapers, puisque le bug ne dépend d'aucun
    d'eux. Ne touche que les groupes réellement scindés dans **ce** lot (plus
    d'une valeur `is_relay` pour un même `(event_name, event_date,
    event_type)`) : une épreuve dont la source publie déjà un classement
    local par heat n'est pas concernée, et y toucher serait sans effet — tri
    stable sur le rang d'origine, donc déjà 1..N ne change pas.

    **Lot partiel (#764)** : une source dont le jeu de lignes rendu varie
    d'un appel à l'autre (mesuré sur ProLiveSport, cf.
    `docs/scrapers/prolivesport.md`) peut présenter un sous-groupe plus petit
    que ce qui est déjà persisté — renuméroter 1..N dessus écraserait un
    classement complet et correct par un classement partiel et faux, sans
    jamais converger. `Course.participation_count`, déjà en base au moment où
    cette fonction tourne (elle précède la persistance du lot), sert de
    garde : un sous-groupe plus petit que le compte persisté n'est pas
    renuméroté — et son `rank_overall` (le rang **combiné** de la source, pas
    encore local) est effacé plutôt que laissé tel quel, sans quoi la fusion
    prudente (`_merge_fields`, qui n'écrase que sur une valeur non vide) le
    prendrait pour un rang local légitime et écraserait le bon rang déjà en
    base. Un rescrape ultérieur au jeu complet renumérotera correctement.

    Limite acceptée : la comparaison porte sur un **compte**, pas sur
    l'ensemble des dossards. Une ligne perdue et une ligne neuve arrivant dans
    le **même** lot pour le même sous-groupe peuvent se compenser en taille —
    le lot resterait alors `>= participation_count` et se ferait renuméroter
    malgré une composition différente de celle persistée. Non traité : la
    coïncidence (perte **et** arrivée simultanées sur le même sous-groupe,
    dans le même lot) est plus étroite que le cas mesuré (#764, une ligne qui
    disparaît simplement), et `participation_count` ne peut que **descendre**
    par suppression manuelle explicite (jamais par un rescrape qui omet une
    ligne, cf. `finalize()` plus bas) — la garde reste donc sûre dans le cas
    dominant.
    """
    groups: dict[tuple[str, object, str], dict[bool, list[ScrapedResult]]] = {}
    for scraped in results:
        key = (scraped.event_name, scraped.event_date, scraped.event_type)
        groups.setdefault(key, {}).setdefault(bool(scraped.is_relay), []).append(scraped)

    for (name, event_date, event_type), by_relay in groups.items():
        if len(by_relay) < 2:
            continue  # pas de scission is_relay pour cette épreuve dans ce lot
        for is_relay, subgroup in by_relay.items():
            course = course_repository.get_by_identity(db, name, event_date, event_type, is_relay)
            if course is not None and len(subgroup) < course.participation_count:
                logger.warning(
                    "Renumérotation solo/relais ignorée pour la course %d %r "
                    "(%s, %s, is_relay=%s) : lot de %d ligne(s) < %d déjà persistées (#764)",
                    course.id, name, event_date, event_type, is_relay,
                    len(subgroup), course.participation_count,
                )
                for scraped in subgroup:
                    scraped.rank_overall = None
                continue
            ranked = sorted(
                (r for r in subgroup if r.rank_overall is not None),
                key=lambda r: r.rank_overall,
            )
            for local_rank, scraped in enumerate(ranked, start=1):
                scraped.rank_overall = local_rank


def _renumber_duplicate_ranks(results: list[ScrapedResult]) -> None:
    """Renumérote `rank_overall` en 1..N par temps quand la source rend un rang
    qui n'est pas global pour cette `Course` (#757, #785).

    Mesuré sur RaceResult (3 façades) : certaines épreuves publient leur champ
    de rang (`AUTORANK`) **par groupe d'affichage** — le genre, le plus
    souvent — et non pour l'épreuve entière. Deux finishers de groupes
    différents peuvent alors partager le même `rank_overall` sans qu'aucun ne
    soit réellement premier (constaté en direct : deux rangs 1, temps
    09:17:39 et 10:28:19), ce qui casse l'hypothèse de
    `services/quality.py::_rank_anomalies` (`ANOMALY_DUPLICATE_RANK`).

    **Opt-in par fournisseur** (#940) : seuls ceux qui déclarent
    `ranks_per_group` (RaceResult) sont concernés. Ailleurs un doublon est
    légitime et reste tel quel : relais RunnerBreizh (une ligne par équipier,
    rang partagé), vrais ex aequo (1, 2, 2, 4) d'une source qui ne classe pas
    strictement au `total_time` (pénalité, temps officiel contre temps puce).
    Pour eux, le finisher se lit au **statut effectif** (`mapping.derive_status`,
    celui de la persistance et de `quality`) : la plupart des scrapers laissent
    le statut d'un finisher vide, et ne le poser qu'à l'écriture laissait le lot
    vide.

    Ne touche que les groupes portant un doublon dans **ce** lot (`Counter`
    sur `rank_overall` des seuls finishers, comme
    `services/quality.py::_rank_anomalies`) : une épreuve dont le rang est
    authentiquement global n'a aucun doublon et sort inchangée. Un DNF/DNS/DSQ
    n'a normalement pas de `rank_overall` (les scrapers, RaceResult compris,
    le mettent à `None`), mais on ne s'y fie pas pour l'inclusion dans le
    lot renuméroté : seul un finisher y entre, sans quoi un rang parasite sur
    un non-finisher entrerait dans le tri par temps.

    Renumérotation par **temps croissant** (`utils.to_seconds(strict=True)`,
    un temps illisible partant en **fin** de classement plutôt qu'à `0` — le
    défaut non strict, pensé pour un cumul, promouvait à tort un temps vide
    au rang 1), et non par tri stable du rang d'origine comme
    `_renumber_relay_split_ranks` (#672) : celui-ci suppose un ordre déjà
    correct mais globalement décalé, ce qui ne tient pas ici — le rang
    d'origine mélange deux ordres indépendants (un par groupe), que seul le
    temps permet de départager.

    Appelée **avant** `_renumber_relay_split_ranks` par les deux points
    d'appel : un tri stable sur un rang déjà doublonné le laisserait tel
    quel (« déjà 1..N » d'après son propre critère), ce qui « uniquifierait »
    silencieusement le doublon avant que ce correctif-ci ait pu le détecter.
    """
    groups: dict[tuple[str, object, str, bool], list[ScrapedResult]] = {}
    for scraped in results:
        key = (
            scraped.event_name, scraped.event_date, scraped.event_type,
            bool(scraped.is_relay),
        )
        groups.setdefault(key, []).append(scraped)

    for group in groups.values():
        ranked = [
            r for r in group
            if r.rank_overall is not None
            and registry.ranks_per_group(r.provider)
            and mapping.derive_status(r).strip().lower() == STATUS_FINISHER
        ]
        rangs = Counter(r.rank_overall for r in ranked)
        if not any(count > 1 for count in rangs.values()):
            continue  # aucun doublon dans ce lot : rang déjà fiable

        def _cle_temps(r: ScrapedResult) -> tuple[bool, int]:
            secondes = to_seconds(r.total_time, strict=True)
            return (secondes is None, secondes or 0)

        ranked.sort(key=_cle_temps)
        for local_rank, scraped in enumerate(ranked, start=1):
            scraped.rank_overall = local_rank


def _persist_challenges(
    db: Session, url: str, held: list[ScrapedResult], persister: "_Persister"
) -> list[ScrapedResult]:
    """Enregistre les heats Challenge appariés (#1008) ; rend les lignes des autres.

    Après `finalize` : l'appariement lit en base les participations du jour,
    celles de ce lot comprises. Un heat qui échoue au test redevient une épreuve.
    """
    groups: dict[tuple, list[ScrapedResult]] = {}
    for scraped in held:
        groups.setdefault((scraped.event_name, scraped.event_date), []).append(scraped)
    leftovers: list[ScrapedResult] = []
    for (name, event_date), rows in groups.items():
        challenge_rows = [ChallengeRow.from_scraped(r) for r in rows]
        found = challenge_service.match(db, challenge_rows, event_date=event_date)
        if found is None:
            leftovers.extend(rows)
            continue
        challenge_service.save(
            db, name=name, event_date=event_date,
            source_url=rows[0].source_url or url, rows=challenge_rows, found=found,
        )
        persister.challenges += 1
        _drop_course_twin(db, name, event_date, {r.source_url or url for r in rows})
    return leftovers


#: Écart toléré entre un Challenge et son jumeau redaté par heat (#1196) : un
#: jour ou deux, jamais une autre édition publiée sous la même URL.
_TWIN_DAYS = 2


def _drop_course_twin(db: Session, name: str, event_date, urls: set[str]) -> None:
    """Supprime l'épreuve qu'un import antérieur a tirée du même heat, faute
    d'épreuves sœurs à l'époque : sinon le heat compterait deux fois (#1008).

    Seule une épreuve publiée sous l'URL du heat en est le jumeau : une homonyme
    d'une autre source n'est pas supprimée par un import, `/admin/doublons` la tranche.
    La date est tolérée à `_TWIN_DAYS` près : `heat_dated` a pu redater le jumeau
    sans redater le Challenge (#1196).
    """
    for course in course_repository.list_named_with_source(db, name, urls):
        if event_date is None or course.event_date is None:
            if course.event_date != event_date:
                continue
        elif abs((course.event_date - event_date).days) > _TWIN_DAYS:
            continue
        logger.info("Course %s replaced by the challenge of the same heat: %s", course.id, name)
        candidates = athlete_repository.only_on_course(db, course.id)
        athlete_ids = participation_repository.athlete_ids_on_course(db, course.id)
        course_repository.delete(db, course)
        db.flush()
        tcn_count_repository.recompute_counts_for_tcn(db, athlete_ids=athlete_ids)
        athlete_repository.delete_orphans_among(db, candidates)


def _prepare_batch(db: Session, url: str, results: list[ScrapedResult]) -> None:
    """Les rattrapages de lot, dans leur ordre, avant la première ligne écrite."""
    _redate_heats(db, results)
    _reclassify_heats(db, url, results)
    _reidentify_heats(db, url, results)
    _renumber_duplicate_ranks(results)
    _renumber_relay_split_ranks(db, results)


def persist_steps(
    db: Session, url: str, results: list[ScrapedResult]
) -> Iterator[tuple[int, "_Persister"]]:
    """Écrit des résultats déjà scrapés, ligne par ligne. **Ne clôt pas la transaction.**

    Seul point d'entrée de la persistance (#914) : les rattrapages de lot, datation
    (#972), classification (#294), renumérotation par doublon de rang (#757, #785)
    puis solo/relais (#672), passent **avant** la première ligne, sinon la seconde
    `Course` est déjà née, ou déjà écrite avec son rang brut, quand on la cherche.
    Le re-scrape admin les sautait en instanciant `_Persister` lui-même.

    Les heats Challenge (#1008) sont mis de côté puis appariés **après** la
    première finalisation, qui a écrit les participations du jour ; ceux qui
    échouent au test repassent par le persister comme des épreuves.

    Rend `(lignes écrites, persister)` : une première fois à 0, puis après chaque
    ligne, pour qu'un flux SSE rapporte sa progression. Le persister est finalisé
    une fois le générateur épuisé.
    """
    held = [r for r in results if heat_is_challenge(r.event_name)]
    results = [r for r in results if not heat_is_challenge(r.event_name)]
    _prepare_batch(db, url, results)
    persister = _Persister(db, url)
    yield 0, persister
    for done, scraped in enumerate(results, start=1):
        persister.add(scraped)
        yield done, persister
    persister.finalize()
    leftovers = _persist_challenges(db, url, held, persister)
    if leftovers:
        _prepare_batch(db, url, leftovers)
        for scraped in leftovers:
            persister.add(scraped)
        persister.finalize()


def persist_results(db: Session, url: str, results: list[ScrapedResult]) -> dict:
    """Écrit des résultats déjà scrapés. **Ne clôt pas la transaction.**

    Le cœur d'`import_event`, extrait pour qu'un appelant qui gère lui-même sa
    transaction puisse l'utiliser (#285) : ni `commit`, ni `rollback`, ni
    `try/except` — l'appelant a des écritures à lui dans la même transaction, et
    c'est à lui de la clore, sur le patron « le service `flush`, la route
    `commit` » du reste du dépôt.

    `courses` est le résumé **brut** du persister : le repli sur les heats
    cachés (`import_dispatch.merge_cached_courses`) appartient au compte rendu d'import, pas à
    l'écriture.
    """
    *_, (_done, persister) = persist_steps(db, url, results)
    return {
        "imported": persister.imported,
        "updated": persister.updated,
        "skipped": persister.skipped,
        "reconciled": persister.reconciled,
        "challenges": persister.challenges,
        "passive_sources": persister.passive_sources,
        "ambiguous_identities": persister.ambiguous_identities,
        "homonyms_created": persister.homonyms_created,
        "courses": persister.courses_summary(),
    }

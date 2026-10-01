"""Accès données pour Athlete — seule couche qui touche la Session pour cette table."""
from collections.abc import Sequence
from datetime import date

from sqlalchemy import (
    and_,
    bindparam,
    case,
    exists,
    false,
    func,
    or_,
    select,
    tuple_,
    union_all,
    update,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core.athlete_identity import athlete_identity_keys
from app.core.club import tcn_clause
from app.core.discipline import federal_clause
from app.core.gender import gender_podium_clause
from app.core.text import deaccent
from app.core.validation import validated_clause
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation, ParticipationTeammate
from app.models.season_validation import SeasonValidation
from app.models.user import User
from app.models.volunteer_action import VolunteerAction
from app.scrapers.base import STATUS_FINISHER


def escape_like(word: str) -> str:
    """Échappe les jokers `LIKE` (`\\`, `%`, `_`) d'un terme utilisateur.

    Extrait de `name_filter` (#484) pour être réutilisé par le classement de
    pertinence de `search_by_relevance` sans dupliquer l'échappement.
    """
    for joker in ("\\", "%", "_"):
        word = word.replace(joker, f"\\{joker}")
    return word


def unaccent_like(column, pattern: str):
    """`column` contient `pattern` (déjà en minuscules, échappé), sans casse ni accents."""
    return func.unaccent(func.lower(column)).like(pattern, escape="\\")


def name_filter(term: str, *, also=None):
    """Filtre nom **ou** prénom d'athlète, mot à mot, sans casse ni accents.

    Chaque mot du terme doit matcher `nom` **ou** `prénom`, en sous-chaîne. Un
    terme d'un seul mot garde donc l'ancien comportement, et « Jean Dupont »
    trouve désormais l'athlète dont le prénom porte « Jean » et le nom
    « Dupont » — impossible tant qu'on testait le terme entier contre chaque
    colonne seule.

    `ilike` seul ne suffit pas : il ignore la casse, jamais les accents, et ce
    sur les deux moteurs. Mesuré — `lower('LEMÉE') LIKE '%lemee%'` vaut faux, y
    compris avec le listener Unicode de `core/database.py`, qui rend `lemée`.

    `also(pattern)` ajoute d'autres colonnes où chaque mot peut aussi se trouver
    (nom d'équipe et équipiers d'un relais, #894).

    `unaccent` désigne l'extension PostgreSQL en production et la fonction
    applicative enregistrée sur la connexion SQLite en développement : même nom,
    donc une seule expression ici. Aucun index n'est utilisable de ce fait, sans
    conséquence — le filtre porte sur une seule épreuve ou une page de résultats.

    Un terme sans mot (blancs seuls, ex. `name=%20`) ne matche **rien** : voir
    le commentaire sur le `false()` de retour.
    """
    clauses = []
    for word in deaccent(term).split():
        word = escape_like(word)
        pattern = f"%{word.lower()}%"
        clauses.append(
            or_(
                unaccent_like(Athlete.nom, pattern),
                unaccent_like(Athlete.prenom, pattern),
                *(also(pattern) if also else ()),
            )
        )
    # Un terme sans mot (blancs seuls, ex. `name=%20`) ne doit rien laisser
    # passer : `false()` empêche `and_(*clauses)` vide de dégénérer en un
    # filtre vide qui rendrait tout le monde — les appelants testent la
    # valeur brute (`if name:`), pas sa version strippée.
    if not clauses:
        return false()
    return and_(*clauses)


def get(db: Session, athlete_id: int) -> Athlete | None:
    return db.get(Athlete, athlete_id)


IdentityKey = tuple[str | None, str | None]


def get_by_identity_keys(db: Session, nom: str, prenom: str) -> Athlete | None:
    """La fiche principale de l'identité de `(nom, prénom)`, quelle que soit sa
    date de naissance (#900)."""
    key = athlete_identity_keys(nom, prenom)
    return get_by_identity_keys_batch(db, [key]).get(key)


def get_by_identity_keys_batch(
    db: Session, keys: Sequence[IdentityKey]
) -> dict[IdentityKey, Athlete]:
    """Résout un lot de clés d'identité en une requête (#706, #907).

    Seules les fiches principales répondent : un homonyme distingué ne reçoit
    de résultat que par geste admin (#967). Une clé vide ne désigne personne.
    Les clés sans correspondance sont absentes du résultat ; à l'appelant de
    créer les fiches manquantes.

    `FOR KEY SHARE` (PostgreSQL ; sans effet sous SQLite) : une fiche résolue ne
    peut plus être supprimée, par une fusion par exemple, avant la fin de la
    transaction qui va y rattacher des résultats. Il ne gêne ni les autres
    imports ni les mises à jour de club et de genre ; il fait attendre un
    renommage (les clés font partie de `uq_athlete_identity`), que
    `admin_actions.update_athlete` borne par `lock_timeout`.
    """
    wanted = {key for key in keys if key[0] is not None}
    if not wanted:
        return {}
    rows = (
        db.query(Athlete)
        .filter(
            tuple_(Athlete.last_name_key, Athlete.first_name_key).in_(wanted),
            Athlete.homonym_rank == 0,
        )
        .with_for_update(read=True, key_share=True)
        .all()
    )
    return {(athlete.last_name_key, athlete.first_name_key): athlete for athlete in rows}


def find_fallback_matches(
    db: Session, keys: Sequence[IdentityKey]
) -> tuple[dict[IdentityKey, Athlete], dict[IdentityKey, list[int]]]:
    """Repli d'identité pour les clés restées sans fiche (#908) : nom et prénom
    inversés, ou nom complet sans prénom face à une fiche découpée (dans les
    deux sens, et dans les deux ordres).

    Ne rattache que sur une correspondance **unique** ; sinon la clé est rendue
    dans le second dictionnaire avec les fiches candidates, pour le rapport.
    L'égalité sur la concaténation des clés couvre tous les découpages d'un nom
    d'un coup.
    """
    wanted = [key for key in keys if key[0] is not None]
    if not wanted:
        return {}, {}
    swapped = {(first, last) for last, first in wanted if first and first != last}
    whole_names = {last for last, first in wanted if not first}
    joined = {joined for last, first in wanted if first for joined in (last + first, first + last)}
    clauses = []
    if swapped:
        clauses.append(tuple_(Athlete.last_name_key, Athlete.first_name_key).in_(swapped))
    if whole_names:
        clauses.append(and_(
            Athlete.first_name_key != "",
            or_(
                (Athlete.last_name_key + Athlete.first_name_key).in_(whole_names),
                (Athlete.first_name_key + Athlete.last_name_key).in_(whole_names),
            ),
        ))
    if joined:
        clauses.append(and_(Athlete.first_name_key == "", Athlete.last_name_key.in_(joined)))
    rows = (
        db.query(Athlete)
        .filter(or_(*clauses), Athlete.homonym_rank == 0)
        .with_for_update(read=True, key_share=True)
        .all()
    )

    matches: dict[IdentityKey, Athlete] = {}
    ambiguous: dict[IdentityKey, list[int]] = {}
    for key in wanted:
        last, first = key
        candidates = {
            athlete.id: athlete for athlete in rows
            if (first and first != last and (athlete.last_name_key, athlete.first_name_key) == (first, last))
            or (not first and athlete.first_name_key and last in (
                athlete.last_name_key + athlete.first_name_key, athlete.first_name_key + athlete.last_name_key
            ))
            or (first and not athlete.first_name_key and athlete.last_name_key in (last + first, first + last))
        }
        if len(candidates) == 1:
            matches[key] = next(iter(candidates.values()))
        elif candidates:
            ambiguous[key] = sorted(candidates)
    return matches, ambiguous


_CREATED_COLUMNS = ("nom", "prenom", "gender", "birth_date", "club")


def create_batch(
    db: Session, athletes_fields: Sequence[dict]
) -> tuple[list[Athlete], set[int]]:
    """Crée un lot de fiches principales, ou rend celles qui existent déjà (#706, #981).

    Un `INSERT … ON CONFLICT DO NOTHING RETURNING` multi-lignes sur
    `uq_athlete_identity`, puis la relecture des seules identités qu'il n'a pas
    insérées : deux imports qui créent la même personne en même temps aboutissent
    à la même fiche. En READ COMMITTED, l'insertion en conflit avec une ligne non
    commitée attend la fin de l'autre transaction ; la relecture voit ensuite sa
    fiche.

    Les lignes partent triées par clé : deux imports qui listent les mêmes
    inconnus dans des ordres différents prennent alors leurs verrous d'insertion
    dans le même ordre, et ne s'interbloquent pas au sein d'une instruction.
    Entre deux tranches d'une même transaction, l'interblocage reste possible ;
    `deadlock_retries` rejoue alors la persistance.

    Rend une fiche par entrée, dans l'ordre, suivie par la session, et les ids
    réellement insérés : une fiche rendue sans l'être existait déjà. Une entrée
    sans identité (`?`, `-`) a des clés NULL, qui ne se heurtent jamais : elle
    est créée par l'ORM.
    """
    unknown = {column for fields in athletes_fields for column in fields} - set(_CREATED_COLUMNS)
    if unknown:
        raise ValueError(f"create_batch does not write {sorted(unknown)}")
    keys = [athlete_identity_keys(fields.get("nom"), fields.get("prenom")) for fields in athletes_fields]
    rows = sorted(
        (
            {
                **{column: fields.get(column) for column in _CREATED_COLUMNS},
                "prenom": fields.get("prenom") or "",
                "gender": fields.get("gender") or "",
                "last_name_key": key[0],
                "first_name_key": key[1],
            }
            for fields, key in zip(athletes_fields, keys, strict=True)
            if key[0] is not None
        ),
        key=lambda row: (row["last_name_key"], row["first_name_key"]),
    )

    by_key: dict[IdentityKey, Athlete] = {}
    inserted_ids: set[int] = set()
    if rows:
        insert = postgresql_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
        inserted = db.scalars(
            insert(Athlete)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["last_name_key", "first_name_key", "homonym_rank"])
            .returning(Athlete)
        ).all()
        by_key = {(athlete.last_name_key, athlete.first_name_key): athlete for athlete in inserted}
        inserted_ids = {athlete.id for athlete in inserted}
        missing = {key for key in keys if key[0] is not None and key not in by_key}
        if missing:
            by_key.update(get_by_identity_keys_batch(db, list(missing)))

    nameless = [Athlete(**fields) for fields, key in zip(athletes_fields, keys, strict=True) if key[0] is None]
    if nameless:
        db.add_all(nameless)
        db.flush()
        inserted_ids.update(athlete.id for athlete in nameless)
    pending_nameless = iter(nameless)
    return (
        [by_key[key] if key[0] is not None else next(pending_nameless) for key in keys],
        inserted_ids,
    )


_HOMONYM_ATTEMPTS = 5


def _highest_homonym_rank(db: Session, key: IdentityKey) -> int:
    """-1 quand la clé n'a aucune fiche : la première créée est alors la principale."""
    return db.scalar(
        select(func.coalesce(func.max(Athlete.homonym_rank), -1)).where(
            Athlete.last_name_key == key[0], Athlete.first_name_key == key[1]
        )
    )


def create_homonym(db: Session, fields: dict) -> Athlete:
    """Crée un homonyme distingué de l'identité de `fields`, au rang suivant (#967).

    Le rang lu peut être pris entre-temps par un import concurrent : l'insertion
    en `ON CONFLICT DO NOTHING` retente alors au rang suivant, quelques fois.
    """
    unknown = set(fields) - set(_CREATED_COLUMNS)
    if unknown:
        raise ValueError(f"create_homonym does not write {sorted(unknown)}")
    key = athlete_identity_keys(fields.get("nom"), fields.get("prenom"))
    if key[0] is None:
        raise ValueError("an athlete without identity has no homonym")
    row = {
        **{column: fields.get(column) for column in _CREATED_COLUMNS},
        "prenom": fields.get("prenom") or "",
        "gender": fields.get("gender") or "",
        "last_name_key": key[0],
        "first_name_key": key[1],
    }
    insert = postgresql_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    rank = _highest_homonym_rank(db, key)
    for _ in range(_HOMONYM_ATTEMPTS):
        rank += 1
        created = db.scalars(
            insert(Athlete)
            .values({**row, "homonym_rank": rank})
            .on_conflict_do_nothing(index_elements=["last_name_key", "first_name_key", "homonym_rank"])
            .returning(Athlete)
        ).first()
        if created is not None:
            return created
    raise RuntimeError(f"no free homonym rank for {key} after {_HOMONYM_ATTEMPTS} attempts")


def apply_updates(db: Session, updates: Sequence[tuple[Athlete, dict[str, str]]]) -> None:
    """Applique des changements de club et de genre en un seul `executemany`,
    dans l'ordre reçu (#980).

    L'appelant les trie par id : deux imports concurrents prennent alors les
    verrous de ligne dans le même ordre, et ne peuvent plus se croiser. Une
    colonne non demandée passe `NULL` et garde sa valeur **en base**
    (`coalesce`) : la réécrire depuis l'instance en mémoire écraserait un club
    commité entre-temps par un autre import ou corrigé par un admin. L'état en
    mémoire suit, sans marquer les instances modifiées : un flush ultérieur
    n'émettrait pas un second UPDATE.
    """
    if not updates:
        return
    table = Athlete.__table__
    statement = (
        update(table)
        .where(table.c.id == bindparam("b_id"))
        .values(
            club=func.coalesce(bindparam("b_club"), table.c.club),
            gender=func.coalesce(bindparam("b_gender"), table.c.gender),
        )
    )
    db.execute(
        statement,
        [
            {"b_id": athlete.id, "b_club": fields.get("club"), "b_gender": fields.get("gender")}
            for athlete, fields in updates
        ],
    )
    for athlete, fields in updates:
        for column, value in fields.items():
            set_committed_value(athlete, column, value)


def latest_club_dates(db: Session, athlete_ids: Sequence[int]) -> dict[int, date]:
    """Date de la plus récente épreuve datée courue sous un club, par athlète (#965).

    Les résultats en attente de validation n'y comptent pas : une déclaration
    en quarantaine ne réécrit pas le club (#915), elle ne le fige pas non plus.
    """
    if not athlete_ids:
        return {}
    rows = db.execute(
        select(Participation.athlete_id, func.max(Course.event_date))
        .join(Course, Course.id == Participation.course_id)
        .where(
            Participation.athlete_id.in_(set(athlete_ids)),
            Participation.club.is_not(None),
            func.trim(Participation.club) != "",
            Course.event_date.is_not(None),
            validated_clause(Participation.is_pending_validation),
        )
        .group_by(Participation.athlete_id)
    )
    return {athlete_id: latest for athlete_id, latest in rows}


def club_is_current(event_date: date | None, latest_club_date: date | None) -> bool:
    """Vrai si le club annoncé par une épreuve du `event_date` devient le club actuel.

    Il faut que l'épreuve soit au moins aussi récente que la dernière épreuve
    datée déjà connue avec un club : sinon réimporter une vieille course
    ramènerait le club de l'époque (#965). Une épreuve sans date ne prouve
    rien, elle ne l'emporte que faute de club daté.
    """
    if latest_club_date is None:
        return True
    return event_date is not None and event_date >= latest_club_date


def resolve(
    db: Session,
    *,
    nom: str,
    prenom: str = "",
    gender: str = "",
    birth_date: date | None = None,
    club: str | None = None,
    update_existing_club: bool = True,
    event_date: date | None = None,
) -> tuple[Athlete, bool]:
    """Retourne (athlète, créé) : `créé` est True si la ligne vient d'être créée.

    `event_date` est la date de l'épreuve qui annonce `club` (`club_is_current`).

    `update_existing_club=False` : `club` ne sert qu'à une fiche neuve. Une
    déclaration en quarantaine ne doit pas réécrire la fiche d'un membre (#915).

    Le repli de réconciliation distingue un **renommage** (cible créée) d'une
    **fusion** (cible préexistante) ; ce drapeau est la seule information qui les
    sépare. `get_or_create` reste le point d'entrée quand le drapeau n'importe pas.
    """
    existing = get_by_identity_keys(db, nom, prenom)
    if existing:
        # Met à jour le club courant si l'épreuve n'est pas plus ancienne que
        # le dernier club connu (#965), et jamais si un humain l'a corrigé : une
        # correction manuelle prime sur tout import ultérieur (#439).
        if (
            update_existing_club and club and existing.club != club and not existing.club_locked
            and club_is_current(event_date, latest_club_dates(db, [existing.id]).get(existing.id))
        ):
            existing.club = club
        # Complète un sexe absent de la première source, sans jamais l'écraser (#964).
        if gender and not existing.gender:
            existing.gender = gender
        return existing, False

    athlete = Athlete(
        nom=(nom or "").strip(),
        prenom=(prenom or "").strip(),
        gender=gender or "",
        birth_date=birth_date,
        club=club,
    )
    db.add(athlete)
    db.flush()  # peuple athlete.id sans commit (la transaction est gérée par le service)
    return athlete, True


def get_or_create(
    db: Session,
    *,
    nom: str,
    prenom: str = "",
    gender: str = "",
    birth_date: date | None = None,
    club: str | None = None,
) -> Athlete:
    """Retourne l'athlète existant (dédoublonné) ou en crée un nouveau (flush pour l'id)."""
    athlete, _ = resolve(
        db, nom=nom, prenom=prenom, gender=gender, birth_date=birth_date, club=club
    )
    return athlete


def search(
    db: Session,
    *,
    name: str | None = None,
    club_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> list[Athlete]:
    q = db.query(Athlete)
    if name:
        q = q.filter(name_filter(name))
    if club_only:
        q = q.filter(tcn_clause(Athlete.club))
    offset = (page - 1) * page_size
    return q.order_by(Athlete.nom, Athlete.prenom).offset(offset).limit(page_size).all()


def search_admin(
    db: Session,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[tuple[Athlete, int]]:
    """Recherche **réservée** : identité complète et nombre de résultats (#117, FR-024).

    Ce que `search()` ne rend pas et qui manque ici : la **date de naissance** et
    le compte de participations. Sur nom + prénom + club seuls, deux vrais
    homonymes du même club sont indiscernables — et le geste censé résorber un
    doublon fusionnerait deux personnes distinctes, sans annulation possible.

    La date de naissance est une donnée personnelle : cette fonction n'a qu'un
    appelant, une route gardée par `athletes:read` (FR-025). La lecture publique
    (`search`) ne l'expose pas et ne doit pas l'exposer.
    """
    lien = credits()
    compte = func.count(lien.c.participation_id)
    requete = (
        db.query(Athlete, compte)
        .outerjoin(lien, lien.c.athlete_id == Athlete.id)
        .group_by(Athlete.id)
    )
    if search:
        requete = requete.filter(name_filter(search))
    offset = (page - 1) * page_size
    lignes = (
        requete.order_by(Athlete.nom, Athlete.prenom).offset(offset).limit(page_size).all()
    )
    return [(athlete, nombre) for athlete, nombre in lignes]


def credits():
    """Couples `(participation_id, athlete_id)` : chaque athlète à qui un résultat revient.

    Le porteur (`Participation.athlete_id`) d'un résultat sans équipiers, ou
    chacun des équipiers d'un relais attribué (#894), porteur compris : aucun
    couple n'est donc compté deux fois.
    """
    sans_equipiers = select(
        Participation.id.label("participation_id"),
        Participation.athlete_id.label("athlete_id"),
    ).where(
        ~exists().where(ParticipationTeammate.participation_id == Participation.id)
    )
    equipiers = select(
        ParticipationTeammate.participation_id.label("participation_id"),
        ParticipationTeammate.athlete_id.label("athlete_id"),
    )
    return union_all(sans_equipiers, equipiers).subquery("credits")


def referenced_outside_results(athlete_id):
    """Vrai si la fiche `athlete_id` est référencée hors des résultats (#901).

    Bénévolats, validations de saison et comptes liés pointent vers
    `athletes.id` sans `ondelete` : une telle fiche n'est pas orpheline, même
    sans participation, et la supprimer lèverait une `ForeignKeyViolation` en
    PostgreSQL (invisible en SQLite, où les FK sont inertes).
    """
    return or_(
        exists().where(VolunteerAction.athlete_id == athlete_id),
        exists().where(SeasonValidation.athlete_id == athlete_id),
        exists().where(User.athlete_id == athlete_id),
    )


def only_on_course(db: Session, course_id: int) -> list[int]:
    """Les athlètes dont **toutes** les participations sont sur cette épreuve (#117).

    Autrement dit : ceux que sa suppression laisserait sans aucun résultat, et
    que la purge de FR-022 emportera (une fiche référencée ailleurs, cf.
    `referenced_outside_results`, n'en est donc pas). Un coureur présent aussi ailleurs n'est pas
    de la liste — « inscrit à cette épreuve » et « n'a que cette épreuve » sont
    deux ensembles différents, et c'est le second que la modale annonce.

    **Lecture pure** : elle chiffre l'impact avant le geste, elle ne prépare rien.

    ponytail: deux ensembles d'ids remontés en mémoire Python puis soustraits —
    ~40 000 tuples sur la plus grosse base envisagée, pour une modale ouverte
    quelques fois par an. Si le volume change de nature, la sortie est un
    `NOT EXISTS` corrélé, qui garde le résultat en base.
    """
    lien = credits()
    inscrits = (
        db.query(lien.c.athlete_id)
        .join(Participation, Participation.id == lien.c.participation_id)
        .filter(Participation.course_id == course_id)
        .filter(~referenced_outside_results(lien.c.athlete_id))
    )
    ailleurs = (
        db.query(lien.c.athlete_id)
        .join(Participation, Participation.id == lien.c.participation_id)
        .filter(Participation.course_id != course_id)
    )
    return sorted({identifiant for (identifiant,) in inscrits} - {identifiant for (identifiant,) in ailleurs})


def delete_orphans_among(db: Session, athlete_ids: list[int] | None = None) -> list[int]:
    """Supprime les athlètes sans participation, **parmi** `athlete_ids`. Rend les ids supprimés.

    Une fiche encore référencée hors des résultats (bénévolat, validation de
    saison, compte lié : `referenced_outside_results`) est **conservée** (#901) :
    elle n'est pas orpheline, et sa suppression violerait une FK en PostgreSQL.

    **`None` et `[]` ne veulent pas dire la même chose**, et la nuance porte tout
    l'intérêt de la fonction : `None` ne restreint rien (le balayage complet
    qu'appelle `delete_orphans`), `[]` désigne un ensemble vide de candidats et
    n'emporte donc personne. Les confondre ferait qu'une suppression d'épreuve
    sans orphelin purgerait tous les orphelins préexistants de la base — hors du
    périmètre du geste, et invisible au journal (#117, FR-013).
    """
    if athlete_ids is not None and not athlete_ids:
        return []
    # Un équipier de relais (#894) n'est référencé que par la liaison : il n'est
    # pas orphelin pour autant.
    requete = (
        db.query(Athlete.id)
        .outerjoin(Participation, Participation.athlete_id == Athlete.id)
        .filter(Participation.id.is_(None))
        .filter(~exists().where(ParticipationTeammate.athlete_id == Athlete.id))
        .filter(~referenced_outside_results(Athlete.id))
    )
    if athlete_ids is not None:
        requete = requete.filter(Athlete.id.in_(athlete_ids))
    orphan_ids = [identifiant for (identifiant,) in requete.all()]
    if not orphan_ids:
        return []
    # Le DELETE revérifie l'absence de participation : un import concurrent a
    # pu en insérer une entre les deux requêtes (#1100). "fetch" purge
    # l'identity map pour que get() retombe à None après suppression.
    supprimes = [
        identifiant
        for (identifiant,) in db.query(Athlete.id)
        .filter(Athlete.id.in_(orphan_ids))
        .filter(~exists().where(Participation.athlete_id == Athlete.id))
        .filter(~exists().where(ParticipationTeammate.athlete_id == Athlete.id))
        .all()
    ]
    if not supprimes:
        return []
    db.query(Athlete).filter(
        Athlete.id.in_(supprimes),
        ~exists().where(Participation.athlete_id == Athlete.id),
        ~exists().where(ParticipationTeammate.athlete_id == Athlete.id),
    ).delete(synchronize_session="fetch")
    return supprimes


def delete_orphans(db: Session) -> int:
    """Balaie **toute** la base et rend le nombre d'athlètes supprimés.

    Contrat inchangé pour son appelant historique : `rescrape_service` l'appelle
    **une fois** en fin de batch (jamais par épreuve — un orphelin après
    l'épreuve A peut être ré-attaché par l'épreuve B) et sérialise son entier
    dans `orphans_removed`.
    """
    return len(delete_orphans_among(db))


def delete_unreferenced(db: Session) -> int:
    """Supprime tous les athlètes que rien ne référence hors des résultats (#384, #994).

    Appelée par `wipe_all_participations` et `wipe_all_courses`, toujours
    **après** avoir vidé `participations` : chaque athlète est alors sans
    résultat, et seules restent les fiches encore référencées par un bénévolat,
    une validation de saison ou un compte (`referenced_outside_results`), que
    PostgreSQL refuserait de supprimer. `DELETE` ensembliste à `NOT EXISTS`
    corrélés, sans liste d'ids : il ne bute pas sur le plafond PostgreSQL de
    65535 paramètres liés que franchirait `delete_orphans_among` sur une base de
    cette taille.
    """
    efface = (
        db.query(Athlete)
        .filter(~referenced_outside_results(Athlete.id))
        .delete(synchronize_session=False)
    )
    db.flush()
    return efface


def count_all(db: Session) -> int:
    """Nombre total de fiches coureur en base (#384)."""
    return db.query(func.count(Athlete.id)).scalar() or 0


def count_unreferenced(db: Session) -> int:
    """Nombre de fiches que `delete_unreferenced` purgerait une fois `participations` vidée.

    Sert à chiffrer l'impact d'une purge totale **avant** de la commettre : même
    prédicat que la purge, pour que l'annonce et l'acte ne divergent pas.
    """
    return (
        db.query(func.count(Athlete.id))
        .filter(~referenced_outside_results(Athlete.id))
        .scalar()
        or 0
    )


def list_with_season_participation_count(
    db: Session,
    *,
    seasons: list[int],
    club_only: bool = False,
    federal_only: bool = False,
) -> list[tuple[Athlete, int, int, int]]:
    """Athlètes avec ≥1 participation sur `seasons`, et trois compteurs distincts (#274, #709).

    Jointure **interne** (à la différence de `search_admin`, qui veut voir les
    athlètes à 0) : c'est elle qui exclut les athlètes sans participation sur le
    filtre demandé. `seasons` vide = pas de restriction de date (Principe V —
    neutralité par défaut), comme `season_clause` de `participation_repository`,
    réutilisée ici plutôt que recopiée. `federal_only` (#382) suit le même
    défaut neutre et la même liste d'exclusion que les fonctions `stats_*` de
    `participation_repository` (#76, #580) — `Course` est déjà jointe sans
    condition ici, contrairement à elles.

    **`club_only` sélectionne le roster sur `Athlete.club`, pas
    `Participation.club`** (#709, research.md D1) : deux fournisseurs ne
    publient jamais l'affiliation club sur la ligne de résultat, et le
    critère précédent (`tcn_clause(Participation.club)`) excluait de la liste
    un membre confirmé du club faute d'affiliation publiée *sur cette
    saison* — pas seulement le sous-comptait. Même critère que
    `athlete_repository.search()`.

    Trois agrégats indépendants sur les mêmes lignes jointes (research.md D2),
    chacun nommé pour ce qu'il compte : `total_count` (toute participation de
    la saison, validée ou non — identique à `list_for_athlete`, FR-001),
    `validated_count` (validées **et** statut `finisher`, FR-002),
    `club_affiliated_count` (idem **et** affiliées au club sur la ligne de
    résultat — comportement historique de cette fonction avant #709, conservé
    à l'identique, FR-003). Le filtre `finisher` (#845) évite qu'un DNS validé
    par un bénévole compte comme participation active — même règle que
    `admin_actions.season_quota`, à garder synchronisées si l'une des deux
    change.
    """
    # Import local : participation_repository importe name_filter d'ici depuis
    # #357, un import en tête de module créerait un cycle.
    from app.repositories.participation_repository import season_clause

    est_valide = and_(
        validated_clause(Participation.is_pending_validation),
        func.lower(Participation.status) == STATUS_FINISHER,
    )
    total = func.count(Participation.id)
    validees = func.sum(case((est_valide, 1), else_=0))
    affiliees_club = func.sum(
        case((and_(est_valide, tcn_clause(Participation.club)), 1), else_=0)
    )
    lien = credits()
    requete = (
        db.query(Athlete, total, validees, affiliees_club)
        .join(lien, lien.c.athlete_id == Athlete.id)
        .join(Participation, Participation.id == lien.c.participation_id)
        .join(Course, Participation.course_id == Course.id)
        .group_by(Athlete.id)
    )
    if club_only:
        requete = requete.filter(tcn_clause(Athlete.club))
    if seasons:
        requete = requete.filter(season_clause(seasons))
    if federal_only:
        requete = requete.filter(federal_clause(Course.event_type))
    # Nom vide (import mal renseigné) en fin de tri, pas en tête (Edge Cases du spec) :
    # sans ce `case`, une chaîne vide précède tout nom non vide en tri lexicographique.
    nom_vide_en_fin = case((Athlete.nom == "", 1), else_=0)
    lignes = requete.order_by(nom_vide_en_fin, Athlete.nom, Athlete.prenom).all()
    return [
        (athlete, int(total_n), int(validees_n), int(affiliees_n))
        for athlete, total_n, validees_n, affiliees_n in lignes
    ]


def update_identity(db: Session, athlete: Athlete, **champs) -> Athlete:
    """Écrit les champs d'identité fournis. **Ne vérifie pas l'unicité** — c'est
    le service qui la contrôle par lecture préalable, pour pouvoir nommer la
    fiche en conflit (#117, FR-005)."""
    for nom_champ, valeur in champs.items():
        setattr(athlete, nom_champ, valeur)
    db.flush()
    return athlete


def _relevance_rank(term: str):
    """Palier de pertinence pour `search_by_relevance` (#484) : 0 = préfixe
    exact, 1 = début de mot après un espace ou un trait d'union, 2 = sous-chaîne
    (déjà tout ce que `name_filter` matchait, sans distinction).

    Combine les conditions sur `nom` et `prenom` en un seul `case()` — évite de
    calculer un rang par champ puis un `LEAST`, absent de SQLite (mesuré : voir
    le design). `min(rang_nom, rang_prenom)` équivaut à « le palier le plus bas
    est atteint si l'une des deux conditions du palier l'est ».
    """
    t = escape_like(deaccent(term).lower())
    nom = func.unaccent(func.lower(Athlete.nom))
    prenom = func.unaccent(func.lower(Athlete.prenom))
    prefixe = or_(nom.like(f"{t}%", escape="\\"), prenom.like(f"{t}%", escape="\\"))
    debut_mot = or_(
        nom.like(f"% {t}%", escape="\\"),
        nom.like(f"%-{t}%", escape="\\"),
        prenom.like(f"% {t}%", escape="\\"),
        prenom.like(f"%-{t}%", escape="\\"),
    )
    return case((prefixe, 0), (debut_mot, 1), else_=2)


def search_by_relevance(
    db: Session, *, term: str, club_only: bool = False, limit: int = 12
) -> list[tuple[Athlete, int]]:
    """Classement pour la palette `⌘K` (#484, NAV-8) : pertinence puis volume.

    À la différence de `search`/`search_admin` (ordonnées `nom, prenom`), le
    tri ici est `_relevance_rank` puis le nombre de participations décroissant
    — le volume ne départage plus qu'à l'intérieur d'un même palier de
    pertinence, jamais entre deux paliers différents.

    `validated_clause` (#562) exclut les résultats en attente du **compte**,
    sans faire disparaître l'athlète : elle vit dans la **condition du
    outerjoin**, pas dans un `.filter()` après coup. Un `.filter()` post-jointure
    dégraderait l'`outerjoin` en jointure interne de fait — la ligne pendante
    serait écartée par le `WHERE`, et un athlète dont l'unique participation
    est pendante n'aurait alors plus aucune ligne jointe du tout, donc
    disparaîtrait de la palette au lieu d'y rester à 0 résultat validé.
    """
    compte = func.count(Participation.id)
    rang = _relevance_rank(term)
    lien = credits()
    requete = (
        db.query(Athlete, compte)
        .outerjoin(lien, lien.c.athlete_id == Athlete.id)
        .outerjoin(
            Participation,
            and_(
                Participation.id == lien.c.participation_id,
                validated_clause(Participation.is_pending_validation),
            ),
        )
        .filter(name_filter(term))
        .group_by(Athlete.id)
    )
    if club_only:
        requete = requete.filter(tcn_clause(Athlete.club))
    return (
        requete.order_by(rang, compte.desc(), Athlete.nom, Athlete.prenom)
        .limit(limit)
        .all()
    )


def _club_roster_requete(db: Session, *, federal_only: bool):
    """Bâtit la requête d'agrégation partagée par `club_roster` et `club_rank`
    (#641) : même tri, même filtrage, pour que le rang calculé au-delà de
    l'aperçu de 12 corresponde exactement à l'ordre affiché.
    """
    # Un podium de relais n'est pas un podium individuel (#894, FR-011) : le
    # relais compte dans le volume `total`, jamais dans les podiums.
    # Relais aussi quand seule l'épreuve est marquée (édition admin) : même
    # critère que `set_teammates`.
    individuel = and_(Participation.is_relay.is_(False), Course.is_relay.is_(False))
    cond_overall = and_(individuel, Participation.rank_overall.between(1, 3))
    # Même règle que le KPI et la liste des podiums (`core.gender`, #936).
    cond_gender = and_(individuel, gender_podium_clause(Participation.rank_gender, Athlete.gender))
    cond_category = and_(individuel, Participation.rank_category.between(1, 3))

    total = func.count(Participation.id)
    podiums = func.sum(case((or_(cond_overall, cond_gender, cond_category), 1), else_=0))
    podiums_overall = func.sum(case((cond_overall, 1), else_=0))
    podiums_gender = func.sum(case((cond_gender, 1), else_=0))
    podiums_category = func.sum(case((cond_category, 1), else_=0))

    lien = credits()
    requete = (
        db.query(Athlete, total, podiums, podiums_overall, podiums_gender, podiums_category)
        .join(lien, lien.c.athlete_id == Athlete.id)
        .join(Participation, Participation.id == lien.c.participation_id)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(tcn_clause(Participation.club))
        .group_by(Athlete.id)
    )
    if federal_only:
        requete = requete.filter(federal_clause(Course.event_type))
    return requete.order_by(total.desc(), podiums.desc(), Athlete.nom, Athlete.prenom), total, podiums


def club_roster(
    db: Session, *, federal_only: bool = False, limit: int = 12
) -> list[tuple[Athlete, int, int, int, int, int]]:
    """Top athlètes du club par volume, podiums ventilés par portée (#581).

    Agrégation entièrement en SQL — aucune participation individuelle n'est
    chargée. `podiums` compte les participations avec au moins un podium
    (dédupliqué) ; `podiums_overall`/`gender`/`category` sont des compteurs
    indépendants, une même participation pouvant incrémenter les trois à la
    fois (cf. #488 côté front, comportement repris à l'identique).
    """
    requete, _total, _podiums = _club_roster_requete(db, federal_only=federal_only)
    return requete.limit(limit).all()


def club_rank(
    db: Session, athlete_id: int, *, federal_only: bool = False
) -> tuple[int, int] | None:
    """Rang (1-based) et taille du club, même ordre que `club_roster` (#641).

    Le rappel épinglé de `/club` (#504) a besoin du rang exact au-delà de
    l'aperçu de 12, sans dupliquer le tri ni charger de participation
    individuelle — `None` si l'athlète n'a aucune participation validée au
    club (absent du roster).
    """
    requete, _total, _podiums = _club_roster_requete(db, federal_only=federal_only)
    ids = [a.id for a, *_ in requete.all()]
    if athlete_id not in ids:
        return None
    return ids.index(athlete_id) + 1, len(ids)


def club_composition(
    db: Session, *, federal_only: bool = False
) -> list[tuple[str, str | None]]:
    """Genre et catégorie d'âge du club entier, un couple par athlète (#642).

    `club_roster` plafonne à 12 (aperçu) ; ici il faut **tout le club**, mais
    sans charger chaque participation individuelle — seul le couple
    genre/catégorie compte. Le genre vient d'`Athlete` (fixe) ; la catégorie
    vient de la participation la plus **récente** (elle change de saison en
    saison), isolée par une fenêtre `row_number()` plutôt que de charger
    l'historique complet pour ne garder que son maximum côté Python — même
    sémantique que `buildRoster` (front, `lib/utils/club-aggregate.ts`).
    """
    rang_recence = (
        func.row_number()
        # `nullslast` : PostgreSQL range sinon une épreuve sans date en tête de
        # `DESC` ; `Participation.id` départage deux épreuves du même jour (#1051).
        .over(
            partition_by=Athlete.id,
            order_by=(Course.event_date.desc().nullslast(), Participation.id.desc()),
        )
        .label("rang_recence")
    )
    lien = credits()
    sous_requete = (
        db.query(
            Athlete.gender.label("gender"),
            Participation.category.label("category"),
            rang_recence,
        )
        .join(lien, lien.c.athlete_id == Athlete.id)
        .join(Participation, Participation.id == lien.c.participation_id)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(tcn_clause(Participation.club))
    )
    if federal_only:
        sous_requete = sous_requete.filter(federal_clause(Course.event_type))
    sous_requete = sous_requete.subquery()
    return (
        db.query(sous_requete.c.gender, sous_requete.c.category)
        .filter(sous_requete.c.rang_recence == 1)
        .all()
    )

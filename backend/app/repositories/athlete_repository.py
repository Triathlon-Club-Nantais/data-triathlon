"""Accès données pour Athlete — seule couche qui touche la Session pour cette table."""
from datetime import date

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.core.club import tcn_clause
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.repositories.participation_repository import season_clause


def get(db: Session, athlete_id: int) -> Athlete | None:
    return db.get(Athlete, athlete_id)


def get_by_identity(
    db: Session, nom: str, prenom: str, birth_date: date | None
) -> Athlete | None:
    """Recherche insensible à la casse sur (nom, prénom, date de naissance)."""
    return (
        db.query(Athlete)
        .filter(
            func.lower(Athlete.nom) == (nom or "").strip().lower(),
            func.lower(Athlete.prenom) == (prenom or "").strip().lower(),
            Athlete.birth_date == birth_date,
        )
        .first()
    )


def resolve(
    db: Session,
    *,
    nom: str,
    prenom: str = "",
    gender: str = "",
    birth_date: date | None = None,
    club: str | None = None,
) -> tuple[Athlete, bool]:
    """Retourne (athlète, créé) : `créé` est True si la ligne vient d'être créée.

    Le repli de réconciliation distingue un **renommage** (cible créée) d'une
    **fusion** (cible préexistante) ; ce drapeau est la seule information qui les
    sépare. `get_or_create` reste le point d'entrée quand le drapeau n'importe pas.
    """
    existing = get_by_identity(db, nom, prenom, birth_date)
    if existing:
        # Met à jour le club courant si l'info est plus récente
        if club and existing.club != club:
            existing.club = club
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
        pattern = f"%{name}%"
        q = q.filter(
            or_(Athlete.nom.ilike(pattern), Athlete.prenom.ilike(pattern))
        )
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
    compte = func.count(Participation.id)
    requete = (
        db.query(Athlete, compte)
        .outerjoin(Participation, Participation.athlete_id == Athlete.id)
        .group_by(Athlete.id)
    )
    if search:
        motif = f"%{search}%"
        requete = requete.filter(
            or_(Athlete.nom.ilike(motif), Athlete.prenom.ilike(motif))
        )
    offset = (page - 1) * page_size
    lignes = (
        requete.order_by(Athlete.nom, Athlete.prenom).offset(offset).limit(page_size).all()
    )
    return [(athlete, nombre) for athlete, nombre in lignes]


def only_on_course(db: Session, course_id: int) -> list[int]:
    """Les athlètes dont **toutes** les participations sont sur cette épreuve (#117).

    Autrement dit : ceux que sa suppression laisserait sans aucun résultat, et
    que la purge de FR-022 emportera. Un coureur présent aussi ailleurs n'est pas
    de la liste — « inscrit à cette épreuve » et « n'a que cette épreuve » sont
    deux ensembles différents, et c'est le second que la modale annonce.

    **Lecture pure** : elle chiffre l'impact avant le geste, elle ne prépare rien.

    ponytail: deux ensembles d'ids remontés en mémoire Python puis soustraits —
    ~40 000 tuples sur la plus grosse base envisagée, pour une modale ouverte
    quelques fois par an. Si le volume change de nature, la sortie est un
    `NOT EXISTS` corrélé, qui garde le résultat en base.
    """
    inscrits = db.query(Participation.athlete_id).filter(
        Participation.course_id == course_id
    )
    ailleurs = db.query(Participation.athlete_id).filter(
        Participation.course_id != course_id
    )
    return sorted({identifiant for (identifiant,) in inscrits} - {identifiant for (identifiant,) in ailleurs})


def delete_orphans_among(db: Session, athlete_ids: list[int] | None = None) -> list[int]:
    """Supprime les athlètes sans participation, **parmi** `athlete_ids`. Rend les ids supprimés.

    `Participation.athlete_id` est la **seule** FK vers `Athlete` : un athlète
    sans participation n'est plus référencé nulle part.

    **`None` et `[]` ne veulent pas dire la même chose**, et la nuance porte tout
    l'intérêt de la fonction : `None` ne restreint rien (le balayage complet
    qu'appelle `delete_orphans`), `[]` désigne un ensemble vide de candidats et
    n'emporte donc personne. Les confondre ferait qu'une suppression d'épreuve
    sans orphelin purgerait tous les orphelins préexistants de la base — hors du
    périmètre du geste, et invisible au journal (#117, FR-013).
    """
    if athlete_ids is not None and not athlete_ids:
        return []
    requete = (
        db.query(Athlete.id)
        .outerjoin(Participation, Participation.athlete_id == Athlete.id)
        .filter(Participation.id.is_(None))
    )
    if athlete_ids is not None:
        requete = requete.filter(Athlete.id.in_(athlete_ids))
    orphan_ids = [identifiant for (identifiant,) in requete.all()]
    if not orphan_ids:
        return []
    # "fetch" purge l'identity map pour que get() retombe à None après suppression
    db.query(Athlete).filter(Athlete.id.in_(orphan_ids)).delete(synchronize_session="fetch")
    return orphan_ids


def delete_orphans(db: Session) -> int:
    """Balaie **toute** la base et rend le nombre d'athlètes supprimés.

    Contrat inchangé pour son appelant historique : `rescrape_service` l'appelle
    **une fois** en fin de batch (jamais par épreuve — un orphelin après
    l'épreuve A peut être ré-attaché par l'épreuve B) et sérialise son entier
    dans `orphans_removed`.
    """
    return len(delete_orphans_among(db))


def list_with_season_participation_count(
    db: Session,
    *,
    seasons: list[int],
    club_only: bool = False,
) -> list[tuple[Athlete, int]]:
    """Athlètes avec ≥1 participation sur `seasons`, et leur compte sur ces saisons (#274).

    Jointure **interne** (à la différence de `search_admin`, qui veut voir les
    athlètes à 0) : c'est elle qui exclut les athlètes sans participation sur le
    filtre demandé. `seasons` vide = pas de restriction de date (Principe V —
    neutralité par défaut), comme `season_clause` de `participation_repository`,
    réutilisée ici plutôt que recopiée.
    """
    compte = func.count(Participation.id)
    requete = (
        db.query(Athlete, compte)
        .join(Participation, Participation.athlete_id == Athlete.id)
        .join(Course, Participation.course_id == Course.id)
        .group_by(Athlete.id)
    )
    if club_only:
        requete = requete.filter(tcn_clause(Participation.club))
    if seasons:
        requete = requete.filter(season_clause(seasons))
    # Nom vide (import mal renseigné) en fin de tri, pas en tête (Edge Cases du spec) :
    # sans ce `case`, une chaîne vide précède tout nom non vide en tri lexicographique.
    nom_vide_en_fin = case((Athlete.nom == "", 1), else_=0)
    lignes = requete.order_by(nom_vide_en_fin, Athlete.nom, Athlete.prenom).all()
    return [(athlete, nombre) for athlete, nombre in lignes]


def update_identity(db: Session, athlete: Athlete, **champs) -> Athlete:
    """Écrit les champs d'identité fournis. **Ne vérifie pas l'unicité** — c'est
    le service qui la contrôle par lecture préalable, pour pouvoir nommer la
    fiche en conflit (#117, FR-005)."""
    for nom_champ, valeur in champs.items():
        setattr(athlete, nom_champ, valeur)
    db.flush()
    return athlete

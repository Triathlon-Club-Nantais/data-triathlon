"""Accès données pour Athlete — seule couche qui touche la Session pour cette table."""
from datetime import date

from sqlalchemy import and_, case, false, func, or_
from sqlalchemy.orm import Session

from app.core.club import tcn_clause
from app.core.discipline import federal_clause
from app.core.text import deaccent
from app.core.validation import validated_clause
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation


def _escape_like(word: str) -> str:
    """Échappe les jokers `LIKE` (`\\`, `%`, `_`) d'un terme utilisateur.

    Extrait de `name_filter` (#484) pour être réutilisé par le classement de
    pertinence de `search_by_relevance` sans dupliquer l'échappement.
    """
    for joker in ("\\", "%", "_"):
        word = word.replace(joker, f"\\{joker}")
    return word


def name_filter(term: str):
    """Filtre nom **ou** prénom d'athlète, mot à mot, sans casse ni accents.

    Chaque mot du terme doit matcher `nom` **ou** `prénom`, en sous-chaîne. Un
    terme d'un seul mot garde donc l'ancien comportement, et « Jean Dupont »
    trouve désormais l'athlète dont le prénom porte « Jean » et le nom
    « Dupont » — impossible tant qu'on testait le terme entier contre chaque
    colonne seule.

    `ilike` seul ne suffit pas : il ignore la casse, jamais les accents, et ce
    sur les deux moteurs. Mesuré — `lower('LEMÉE') LIKE '%lemee%'` vaut faux, y
    compris avec le listener Unicode de `core/database.py`, qui rend `lemée`.

    `unaccent` désigne l'extension PostgreSQL en production et la fonction
    applicative enregistrée sur la connexion SQLite en développement : même nom,
    donc une seule expression ici. Aucun index n'est utilisable de ce fait, sans
    conséquence — le filtre porte sur une seule épreuve ou une page de résultats.

    Un terme sans mot (blancs seuls, ex. `name=%20`) ne matche **rien** : voir
    le commentaire sur le `false()` de retour.
    """
    clauses = []
    for word in deaccent(term).split():
        word = _escape_like(word)
        pattern = f"%{word.lower()}%"
        clauses.append(
            or_(
                func.unaccent(func.lower(Athlete.nom)).like(pattern, escape="\\"),
                func.unaccent(func.lower(Athlete.prenom)).like(pattern, escape="\\"),
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
        # Met à jour le club courant si l'info est plus récente — sauf si un
        # humain l'a corrigé : une correction manuelle prime sur tout import
        # ultérieur, y compris celui d'une course d'il y a trois ans qui annonce
        # le club de l'époque (#439). Le drapeau est un attribut de la ligne déjà
        # chargée : le lire ne coûte aucune requête de plus à l'import.
        if club and existing.club != club and not existing.club_locked:
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
    compte = func.count(Participation.id)
    requete = (
        db.query(Athlete, compte)
        .outerjoin(Participation, Participation.athlete_id == Athlete.id)
        .group_by(Athlete.id)
    )
    if search:
        requete = requete.filter(name_filter(search))
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

    `Participation.athlete_id` est la seule FK vers `Athlete` **jamais peuplée**
    (`users.athlete_id` existe mais rien dans `app/` ne l'écrit) : un athlète
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


def delete_all(db: Session) -> int:
    """Supprime **tous** les athlètes de la base. Rend le nombre effacé (#384).

    Appelée par `wipe_all_participations` et `wipe_all_courses`, toujours
    **après** avoir vidé `participations` (directement, ou par cascade
    depuis `Course`) — à ce moment, chaque athlète est orphelin par
    construction (`Participation.athlete_id` est la seule FK vers `Athlete`
    jamais peuplée), donc « tous les athlètes » et « tous les orphelins »
    désignent le même ensemble. Un `DELETE` sans `WHERE` évite le plafond
    PostgreSQL de 65535 paramètres liés que franchirait `delete_orphans_among`
    sur une base de cette taille (elle matérialise chaque id en mémoire puis
    les repasse un par un dans un `IN (...)`).
    """
    efface = db.query(Athlete).delete(synchronize_session=False)
    db.flush()
    return efface


def count_all(db: Session) -> int:
    """Nombre total de fiches coureur en base (#384).

    Sert à chiffrer l'impact d'une purge totale des résultats **avant** de la
    commettre : vider `Participation` entièrement laisse *tout* athlète
    orphelin (`Participation.athlete_id` est sa seule FK jamais peuplée, cf.
    `delete_orphans_among` ci-dessus), donc ce compte est exactement celui que
    `delete_all` purgera.
    """
    return db.query(func.count(Athlete.id)).scalar() or 0


def list_with_season_participation_count(
    db: Session,
    *,
    seasons: list[int],
    club_only: bool = False,
    federal_only: bool = False,
) -> list[tuple[Athlete, int]]:
    """Athlètes avec ≥1 participation sur `seasons`, et leur compte sur ces saisons (#274).

    Jointure **interne** (à la différence de `search_admin`, qui veut voir les
    athlètes à 0) : c'est elle qui exclut les athlètes sans participation sur le
    filtre demandé. `seasons` vide = pas de restriction de date (Principe V —
    neutralité par défaut), comme `season_clause` de `participation_repository`,
    réutilisée ici plutôt que recopiée. `federal_only` (#382) suit le même
    défaut neutre et la même liste d'exclusion que les fonctions `stats_*` de
    `participation_repository` (#76, #580) — `Course` est déjà jointe sans
    condition ici, contrairement à elles.
    """
    # Import local : participation_repository importe name_filter d'ici depuis
    # #357, un import en tête de module créerait un cycle.
    from app.repositories.participation_repository import season_clause

    compte = func.count(Participation.id)
    requete = (
        db.query(Athlete, compte)
        .join(Participation, Participation.athlete_id == Athlete.id)
        .join(Course, Participation.course_id == Course.id)
        # #562 : jointure interne, comme le reste de cette fonction — un
        # `.filter()` suffit, pas de piège d'`outerjoin` ici.
        .filter(validated_clause(Participation.is_pending_validation))
        .group_by(Athlete.id)
    )
    if club_only:
        requete = requete.filter(tcn_clause(Participation.club))
    if seasons:
        requete = requete.filter(season_clause(seasons))
    if federal_only:
        requete = requete.filter(federal_clause(Course.event_type))
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


def _relevance_rank(term: str):
    """Palier de pertinence pour `search_by_relevance` (#484) : 0 = préfixe
    exact, 1 = début de mot après un espace ou un trait d'union, 2 = sous-chaîne
    (déjà tout ce que `name_filter` matchait, sans distinction).

    Combine les conditions sur `nom` et `prenom` en un seul `case()` — évite de
    calculer un rang par champ puis un `LEAST`, absent de SQLite (mesuré : voir
    le design). `min(rang_nom, rang_prenom)` équivaut à « le palier le plus bas
    est atteint si l'une des deux conditions du palier l'est ».
    """
    t = _escape_like(deaccent(term).lower())
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
    requete = (
        db.query(Athlete, compte)
        .outerjoin(
            Participation,
            and_(
                Participation.athlete_id == Athlete.id,
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

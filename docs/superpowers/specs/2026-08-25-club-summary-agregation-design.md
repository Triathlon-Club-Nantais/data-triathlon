# Agrégation serveur de `/club` — issue #581

Design brainstormé le 2026-08-25. Périmètre : la partie `/club` de #581 (la
partie `/dashboard`, `page_size: 200 → 6`, est un correctif d'une ligne traité
hors plan, voie « sans plan »).

## Le problème

`/club` demande `GET /participations?scope=club&page_size=5000` (mesuré :
2126 ko de JSON) pour n'afficher que 4 compteurs, un aperçu de 12 fiches de
roster, une liste de podiums et 6 résultats récents. Le tableau complet est
sérialisé dans la charge RSC vers `ClubPodiumKpi` et `PodiumsList`, deux
composants client qui le reçoivent **entier** pour recalculer sur `?rank=`
sans re-fetch (#132). `CLUB_PARTICIPATIONS_PAGE_SIZE` (5000) est le plafond de
l'API, pas un choix : en-dessous, roster et KPI se tronquent **sans le dire**.

`frontend/AGENTS.md` documente déjà la sortie : l'agrégation côté serveur
(#274, #382). Ce design la met en œuvre.

## Ce que ce lot ne fait pas

- **Ne rejuge pas `pushState` vs `router.push`** sur `?rank=` (piste 2 de
  l'issue). `ClubPodiumKpi` et `PodiumsList` restent des composants client
  lisant `?rank=` via `useSearchParams` : c'est leur **payload** qui change,
  pas leur mécanique de mise à jour. `RankTypeToggle` ne bouge pas.
- **Ne plafonne pas la liste de podiums.** `PodiumsList` promet déjà « voir les
  N autres podiums » = la totalité, pas un top-N — un plafond côté requête
  romprait ce contrat en silence, exactement ce que l'issue reproche à
  `CLUB_PARTICIPATIONS_PAGE_SIZE`.
- **Ne touche pas `GET /stats` ni `stats_service.get_stats`.** Les trois
  premiers KPI et `stats.rank_counters` (#376) couvrent déjà tout ce dont
  `/club` a besoin pour eux ; ce lot les **consomme** enfin depuis `/club`, il
  ne les modifie pas.

## Vue d'ensemble

`/club` passe de 2 requêtes (`getStats` + `listParticipations(page_size=5000)`)
à 3, aucune ne dépassant quelques ko :

| Besoin de l'écran | Source | Nouveau ? |
| --- | --- | --- |
| 3 KPI (résultats/athlètes/épreuves) | `GET /stats` | non |
| Décompte « Podiums » par mode de rang | `stats.rank_counters` | non — juste câblé enfin |
| Roster (aperçu 12) | `GET /club/summary` → `roster` | **oui** |
| Liste de podiums (4 modes, complète) | `GET /club/summary` → `podiums` | **oui** |
| 6 résultats récents | `GET /participations?scope=club&page_size=6` | non — juste `page_size` réduit |

## 1. Backend — `GET /club/summary`

Nouveau routeur `app/api/v1/club.py`, monté dans `router.py` comme les autres.
Toujours club-scopé (comme la page elle-même — « TOUJOURS filtrée sur le
club », `club/page.tsx`), donc pas de paramètre `scope` : un seul,
`federal_only`, même défaut neutre que `for_stats`/`list_with_season_participation_count`.

```python
@router.get("/club/summary", response_model=ClubSummary)
def get_club_summary(
    federal_only: bool = Query(False, description="Retire trail, course à pied et cyclisme."),
    db: Session = Depends(get_db),
):
    roster = athlete_repository.club_roster(db, federal_only=federal_only)
    podiums = participation_repository.club_podiums(db, federal_only=federal_only)
    return ClubSummary(roster=roster, podiums=podiums)
```

### 1a. Roster — `athlete_repository.club_roster()`

Mirroir de `list_with_season_participation_count` (#274) : `GROUP BY`
athlète, agrégats en SQL, aucune participation chargée entière. Toujours
`club_only=True` implicite, pas de filtre saison (le roster de `/club` est
all-time, comme `stats` appelé sans `seasons`).

```python
def club_roster(db: Session, *, federal_only: bool = False, limit: int = 12) -> list[tuple]:
    """Top athlètes du club par volume, avec leurs podiums ventilés (#581)."""
    podium = lambda col: func.sum(case((and_(col >= 1, col <= 3), 1), else_=0))
    requete = (
        db.query(
            Athlete,
            func.count(Participation.id),
            podium(Participation.rank_overall),
            podium(Participation.rank_gender),
            podium(Participation.rank_category),
        )
        .join(Participation, Participation.athlete_id == Athlete.id)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(tcn_clause(Participation.club))
        .group_by(Athlete.id)
    )
    if federal_only:
        requete = requete.filter(federal_clause(Course.event_type))
    return (
        requete.order_by(desc("count_1"), desc("count_2"), Athlete.nom, Athlete.prenom)
        .limit(limit)
        .all()
    )
```

(Le tri exact des colonnes agrégées en SQLAlchemy dépendra de la syntaxe
retenue à l'implémentation — `func.count(...).label("total")` etc. — point de
détail, pas d'architecture.)

**Simplification actée en brainstorming** : `RosterEntry.lastDate`/`lastEvent`
existent côté front (`lib/utils/club-aggregate.ts`) mais **ne sont rendus nulle
part** dans `ClubDashboard` — seuls `count`, `podiums`, `podiumsByScope` le
sont. La requête ne les calcule donc pas (pas de fenêtre `ROW_NUMBER`, pas de
sous-requête corrélée). Le total du roster pour le texte « Les athlètes les
plus actifs » vient de `stats.athletes`, déjà chargé.

`ClubRosterEntry` (schéma) : `athlete_id, prenom, nom, count, podiums,
podiums_overall, podiums_gender, podiums_category`. `podiums` = nombre de
participations avec au moins un podium (peut différer de la somme des trois,
une participation pouvant être podium sur plusieurs portées à la fois — même
sémantique que `RosterEntry.podiums` actuel).

### 1b. Podiums — `participation_repository.club_podiums()`

Une seule requête filtrée (pas un `GROUP BY` — on veut les lignes, pas un
compte), sur les colonnes utiles seulement (jamais l'entité `Participation`
complète, même logique que `summary_rows_for_course`) :

```python
def club_podiums(db: Session, *, federal_only: bool = False) -> list[Row]:
    """Participations podium (rang ≤3 sur au moins une portée), club (#581)."""
    q = (
        db.query(
            Participation.id, Participation.rank_overall, Participation.rank_gender,
            Participation.rank_category, Participation.total_time,
            Athlete.id, Athlete.prenom, Athlete.nom,
            Course.name, Course.event_type, Course.is_relay, Course.event_date,
        )
        .join(Athlete, Participation.athlete_id == Athlete.id)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(tcn_clause(Participation.club))
        .filter(or_(
            Participation.rank_overall.between(1, 3),
            Participation.rank_gender.between(1, 3),
            Participation.rank_category.between(1, 3),
        ))
    )
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q.all()
```

Le bucketing par mode (`scratch`/`category`/`gender`/`all`) et le tri
(rang asc puis date desc) se font en Python sur ces lignes déjà filtrées —
même sémantique que `listPodiums`/`bestRank` du front aujourd'hui (« all » =
meilleur des trois rangs), portée dans une fonction pure du service, testable
isolément (miroir de `_rank_counters`). Le nombre de lignes que cette requête
retourne est borné par nature (rang ≤3), sans rapport avec le volume total de
participations du club.

`ClubPodiumEntry` (schéma) : `participation_id, athlete_id, athlete_name,
event_name, event_type, is_relay, event_date, rank, scope, total_time`.
`ClubPodiums` : `{scratch: [...], category: [...], gender: [...], all: [...]}`.

## 2. Frontend

### `club/page.tsx`

```ts
const [stats, summary, recent] = await Promise.all([
  apiServer.getStats({ scope: SCOPE_CLUB, federal_only }, revalidateOpts),
  apiServer.getClubSummary({ federal_only }, revalidateOpts),
  apiServer.listParticipations({ scope: SCOPE_CLUB, federal_only, page_size: 6 }, revalidateOpts),
]);
```

`ClubDashboard` reçoit `{ stats, summary, recent }` au lieu de `{ stats,
participations }`.

### `ClubDashboard.tsx`

- Roster : `summary.roster.map(...)` directement (déjà plafonné à 12
  côté serveur — plus de `.slice(0, APERCU_ROSTER)`, `APERCU_ROSTER` disparaît
  avec son usage de troncature d'affichage — sa valeur (12) migre en paramètre
  `limit` de `club_roster`).
- « Résultats récents » : `recent.map(...)` directement — `recentParticipations()`
  n'est plus appelé ici (la requête backend trie déjà par `created_at desc`).
- **Bandeau de troncature (`tronque`, `CLUB_PARTICIPATIONS_PAGE_SIZE`) :
  supprimé**, pas ajusté. Roster et podiums sont désormais exacts (pas de
  plafond) ; « récents » n'a jamais prétendu être exhaustif.

### `ClubPodiumKpi.tsx`

Prend `rankCounters: DashboardRankCounters` (le type que `StatCardsRank`
consomme déjà) au lieu de `participations`. Même règle que `StatCardsRank`
pour le mode `gender` (somme `women.podiums + men.podiums`) :

```ts
export function ClubPodiumKpi({ rankCounters }: { rankCounters: DashboardRankCounters }) {
  const rankType = rankTypeFromParam(useSearchParams().get(RANK_PARAM) ?? undefined);
  const count = rankType === "gender"
    ? rankCounters.gender.women.podiums + rankCounters.gender.men.podiums
    : rankCounters[rankType].podiums;
  ...
}
```

### `PodiumsList.tsx`

Prend `podiums: ClubPodiums` au lieu de `participations`. Le bucket courant
(`podiums[rankType]`) remplace `listPodiums(participations, rankType)` — même
lecture de `?rank=`, même état `etendu`/`APERCU_PODIUMS`. Le rendu de chaque
entrée s'appuie sur les champs plats du `ClubPodiumEntry` (`athlete_name`,
`event_name`, `event_type`, `is_relay`, `rank`, `scope`, `total_time`) au lieu
de `p.athlete?.…`/`p.course.…`.

### Code mort supprimé

`lib/utils/club-aggregate.ts` perd `buildRoster`, `clubSummary`, `bestRank`,
`isPodium`, `bestPodiumRank`, `listPodiums`, `isTopN`, `BestRank`,
`PodiumEntry` (interne), `RosterEntry` — aucun n'a d'appelant restant en
dehors de ce fichier et des deux composants réécrits (vérifié : `EventsTable.tsx`,
seul autre importeur du module, n'utilise que `recentParticipations`,
conservée — le fichier n'exporte plus qu'elle après ce lot). Le type
`PodiumScope` déménage vers `lib/podium-scope.ts`, qui porte déjà
`PODIUM_SCOPE_META` sur les mêmes trois valeurs — les nouveaux types front
`ClubRosterEntry`/`ClubPodiumEntry` (miroir des schémas Pydantic) rejoignent
`lib/types.ts`, à côté de `Stats`/`DashboardRankCounters`.

`lib/club.ts` perd `CLUB_PARTICIPATIONS_PAGE_SIZE` et son commentaire.

## 3. Cas limites

- **Club sans résultat** : `roster` et chaque bucket de `podiums` sont des
  listes vides — `ClubDashboard` garde son `EmptyState` existant, piloté par
  `participations.length === 0` aujourd'hui → devient `stats.total === 0`
  (déjà le cas sur `/dashboard`).
- **`federal_only`** : filtré identiquement dans les deux nouvelles requêtes
  et dans `getStats`/`listParticipations` — même `federal_clause` partagée.
- **Participations en attente de validation** : exclues par `validated_clause`
  dans les deux nouvelles requêtes, comme partout ailleurs (#270).

## 4. Tests

- Backend : tests de repository pour `club_roster` (tri, limite, `federal_only`,
  exclusion des participations en attente, ventilation des podiums par
  portée) et `club_podiums` (bucketing par mode, sémantique « all » = meilleur
  rang, `federal_only`) ; test d'API pour `GET /club/summary` (club vide,
  forme de la réponse).
- Frontend : `ClubDashboard.test.tsx`, `PodiumsList.test.tsx`, `ClubPodiumKpi.test.tsx`
  (à vérifier s'ils existent déjà — sinon ajout), `club/page.test.tsx` adaptés
  aux nouvelles props/routes mockées ; suppression des cas de test de
  `club-aggregate.test.ts` couvrant les fonctions supprimées.

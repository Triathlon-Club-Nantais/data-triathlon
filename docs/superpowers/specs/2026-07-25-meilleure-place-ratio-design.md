# Meilleure place d'un athlète : ratio et nombre de participants

Issue : [#80](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/80)

## Problème

Sur la fiche athlète, « Meilleure place » affiche le rang absolu minimum. Un 20e
sur 80 y écrase un 42e sur 300, alors que la seconde performance situe l'athlète
plus haut dans son champ. Le rang seul n'est pas comparable d'une course à
l'autre : il faut le rapporter au nombre de classés.

Par ailleurs le tableau « Toutes les épreuves » affiche « 42e » sans dire sur
combien — l'information manque au lecteur pour interpréter la place.

## Décisions

### Population comptée

Le dénominateur est le nombre de **finishers classés du même groupe** :
participations d'une course avec `status == "finisher"` **et** `rank_overall`
non nul, restreintes au même `is_relay` que la participation affichée.

C'est la seule population cohérente avec `rank_overall` : les DNF/DNS/DSQ n'ont
pas de rang, et solos et relais sont classés séparément (deux « rang 1 »
légitimes dans une même course — cf. `services/quality.py::_rank_anomalies`).
« 42e / 300 » se lit donc « 42e sur 300 classés ».

### Données incohérentes

La base est alimentée par scraping : un import partiel peut laisser un athlète
au rang 42 dans une course où seuls 20 finishers sont en base. Dans ce cas —
`rank_overall > total` — on **masque le ratio et le percentile**, la ligne
retombe sur la place seule, comme aujourd'hui. Un « Top 210 % » est pire que pas
de ratio, et ces courses ressortent déjà comme non fiables côté admin
(`Course.is_reliable`).

Même repli quand `total < 2` : un « 1er / 1 — Top 100 % » ne signale rien
d'autre qu'un import incomplet.

### Deux tuiles, pas une

« Meilleure place » conserve son sens actuel (`min(rank_overall)`) et une tuile
« Meilleur ratio » est ajoutée à côté. Les deux peuvent désigner des courses
différentes — c'est le propos de l'issue, et le lecteur voit les deux lectures
plutôt qu'un arbitrage silencieux.

### Périmètre

Fiche athlète uniquement (`/athletes/[id]`). C'est l'écran de la capture de
l'issue et le seul où le ratio a du sens : comparer les courses entre elles
pour un même athlète. La page `/resultats` et la fiche course ne bougent pas.

## Architecture

### Backend

Le compte remonte par la **seule route `GET /athletes/{id}`**, enrichie d'un
agrégat borné aux courses de l'athlète. Deux alternatives écartées :

- porter `finishers_count` sur `CourseBrief` ferait payer une sous-requête
  corrélée à `/participations` (liste paginée) et `/courses` pour un besoin d'un
  seul écran ;
- dénormaliser une colonne sur `Course` ajouterait migration, backfill et un
  invariant à maintenir à chaque ré-import ou upsert.

**`repositories/participation_repository.py`**

```python
def finishers_count_by_group(db, course_ids) -> dict[tuple[int, bool], int]
```

Une requête : `COUNT(*)` sur les participations de `course_ids` où
`status == "finisher"` et `rank_overall IS NOT NULL`, groupée par
`(course_id, is_relay)`. Retourne `{}` pour une liste vide, sans requête.

**`schemas/participation.py`**

```python
class AthleteParticipationOut(ParticipationOut):
    course_finishers: int | None = None
```

`ParticipationOut` reste inchangé : aucune autre route n'est touchée.

**`api/v1/athletes.py`**

Après `list_for_athlete`, un appel au repo, puis attachement du compte à chaque
participation via sa clé `(course_id, is_relay)`. `None` si la clé est absente
(course sans aucun finisher classé).

Le backend renvoie **le compte seul** — ni pourcentage ni repli : ce sont des
règles de présentation, elles vivent côté front où elles sont testées avec le
rendu.

### Frontend

**`lib/utils/ranking.ts`** (nouveau, à côté de `club-aggregate.ts`)

- `rankRatio(p) → { rank, total, percent } | null` — `null` si `rank_overall`
  absent, `course_finishers` absent ou nul, `rank > total`, ou `total < 2`.
- `percent = Math.ceil(rank / total * 100)` — colle aux exemples de l'issue
  (42/300 → 14, 20/80 → 25) et n'affiche jamais « Top 0 % ».
- `bestRatio(participations)` — sélection sur le ratio **brut** (non arrondi),
  départage par le rang absolu le plus petit.

**`components/tcn/StatCard.tsx`**

Ajout d'une prop `hint?: ReactNode` au variant `default` : sous-ligne 13 px en
`--tcn-text-faint`, sous le trait orange. Le variant `hero` garde son `delta`,
inchangé.

**`app/athletes/[id]/page.tsx`**

Grille de 4 → 5 tuiles, `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5` :

```
Épreuves │ Meilleure place │ Meilleur ratio │ Top 10 │ Format favori
   12    │      20e        │    TOP 14%     │   3    │    Tri S
         │                 │ 42e sur 300    │        │
```

« Meilleur ratio » : `TOP n%` en `--tcn-orange`, `hint` = « 42e sur 300 » (le
libellé exact du rendu ci-dessus). `—` sans hint si aucune course n'est
exploitable.

Colonne « Place » du tableau : `PlaceBadge` suivi de `/300` en gris discret ;
largeur de colonne `90px → 120px` dans `COLS`. Le percentile n'apparaît **pas**
sur la ligne — la colonne est étroite, `/300` porte l'information brute, et le
percentile trouve sa place dans la tuile.

## Tests

**Backend**

- `finishers_count_by_group` : solos et relais comptés séparément ; DNF/DNS/DSQ
  exclus ; finishers sans `rank_overall` exclus ; course sans participation
  absente du dictionnaire ; liste d'ids vide.
- Route `GET /athletes/{id}` : `course_finishers` présent et juste ;
  `null` quand la course n'a aucun finisher classé.

**Frontend**

- `ranking.test.ts` : cas nominal, rang absent, compte absent, `rank > total`,
  `total < 2`, sélection du meilleur ratio, départage à ratio égal.
- Test de page athlète sur le modèle de `app/dashboard/page.test.tsx` : tuile
  « Meilleur ratio » rendue, colonne `/N` présente, repli sur la place seule
  quand les données sont incohérentes.

# Classification : discipline natation (#1743) et repli à vérifier (#1744)

Lot « classification » du jalon v0.9.0, remonté par #1738. Les deux bugs du lot
(#1742 mots clés manquants, #1745 correction manuelle écrasée) sont traités à part,
en voie sans plan ; ce document couvre les deux features.

## Pourquoi

Le partage triathlon / autres disciplines repose sur le type déduit du **nom**
(`classify_event_type`). Deux angles morts font compter à tort une épreuve comme
triathlon :

1. aucune discipline natation n'existe, une traversée à la nage sort en
   `triathlon` ou en `course-a-pied-5k` (#1743) ;
2. quand le nom ne nomme aucun sport, le classifieur se replie sur `triathlon`
   sans trace : les 9 « Cyclathlon La Chaussaire » de prod sont passées inaperçues
   pendant deux mois (#1744).

Succès : une épreuve de natation est exclue des compteurs par défaut ; une épreuve
typée par le repli apparaît dans une liste admin jusqu'à ce qu'on corrige son type.

## Non-objectifs

- Des tailles de natation (`natation-5k`), un scraper FFN.
- Changer la valeur du repli, exclure automatiquement une épreuve marquée.
- Une interface pour annuler une correction manuelle.

## #1743, discipline natation

- Slug `natation` ajouté à `CANONICAL_TYPES` et à `BARE_TYPES`, sans taille.
- Le classifieur produit `natation` pour un nom portant `natation`, `nage` (mot
  entier seulement, *mon choix* : pas `nager`/`nageur`) ou `eau libre`,
  **après** les multisports (`swimrun`, `swim-bike`, `aquathlon`, `aquarun`) et
  `triathlon`, **avant** les mono-sports : `Championnat natation eau libre 5 km`
  ne doit plus tomber dans `_running_slug` à cause de « 5 km ».
- `natation` dans `DEFAULT_NON_FEDERAL_DISCIPLINES`
  (`backend/app/core/counter_scope.py`) **et** une migration de données qui pose
  l'entrée en base : un simple `INSERT` dans `counter_scope_entries`,
  `kind = NON_FEDERAL_DISCIPLINE`, `value = 'natation'`, `created_by_user_id`
  NULL (ligne d'amorçage), `DELETE` symétrique au downgrade. La base fait foi
  une fois chargée, d'où la ligne ; `tests/test_migrations.py` (~715) vérifie que
  défauts et lignes amorcées coïncident.
- Front : libellé « Natation » dans `frontend/lib/constants.ts` (table des
  libellés, liste des disciplines de saisie si les autres mono-sports y sont),
  couleur dans `frontend/lib/sport-colors.ts` (variable `--swim` si elle existe,
  à la manière dont le cyclisme et la course à pied y sont rangés), abréviation
  dans `frontend/lib/utils/format.ts` si les autres disciplines en ont une.
- Tests : les deux noms de l'issue, et un `swimrun` / `aquathlon` qui portent
  « nage » ou « eau libre » restent ce qu'ils sont.

## #1744, repli à vérifier

### Support du marquage (décidé par l'utilisateur)

La colonne `Course.event_type_origin` posée par #1745 (`'classified'` par défaut,
`'manual'` après une correction admin) reçoit une troisième valeur, `'fallback'`.
Pas de nouvelle colonne, `quality_issues` n'est pas détourné. Une correction
admin passe l'origine à `'manual'` et fait donc sortir l'épreuve de la liste
d'elle-même.

### Quand une épreuve est « fallback »

À l'import (création comme ré-import), pour chaque épreuve d'origine non `manual` :

- son `event_type` est un `triathlon` ou `triathlon-<taille>` ;
- son **nom** ne nomme aucun sport. Le nom d'une épreuve porte déjà le titre de
  l'événement (`« <Épreuve> - <Heat> »`), il tient donc lieu du `context` que le
  scraper a passé au classifieur. Le test se fait par une fonction publique de
  `classify.py` (exposer `_sport_base` sous un nom public, par exemple
  `names_a_sport(text) -> bool`), sans changer la signature de
  `classify_event_type` ni toucher aux 15 scrapers. Les jetons qui valent
  triathlon sans le dire comptent comme un sport nommé, **dans cette fonction
  seulement** (le classifieur n'en change pas) : le mot entier `tri`, `ironman`,
  `embrunman`, `triman` (Chtriman, Altriman), `70.3`. Un mot de taille seul
  (`Sprint`, `Format S`) non, c'est précisément le repli ;
- aucun résultat de cette épreuve ne porte à la fois un temps de natation **et**
  un temps de vélo (corroboration par les splits, demandée par l'issue). Un seul
  résultat suffit. Côté import, `ScrapedResult.swim_time` et `bike_time` ;
  côté base, les clés `swim` et `bike` de `Participation.splits` (mesuré sur la
  base locale). Un seul prédicat partagé entre les deux chemins.

**Mesuré sur la prod le 21/10/2026** (lecture seule) : 508 épreuves `triathlon*`,
63 dont le nom ne nomme aucun sport au sens de `_sport_base`, 35 d'entre elles
sans résultat natation + vélo. Avec les jetons ci-dessus, il en reste 25, toutes
de vrais mauvais classements : Armorun 2025/2026 (10), Biathlon de Damgan 2025
(3), L'Aqua'Rantec 2025 (3), Cyclathlon La Chaussaire (9, reclassés par #1742).
Les 28 sans sport nommé mais avec splits (IRONMAN, Altriman, SILLON X-RACE…) sont
bien des triathlons : la corroboration par les splits est indispensable.

*Limite connue* : un fournisseur qui nommerait l'épreuve sans le titre de
l'événement ferait marquer à tort un triathlon au heat neutre (« Open »). Aucun
cas en prod aujourd'hui. Le coût est un faux positif dans une liste de revue,
jamais un mauvais compteur ; l'admin le sort de la liste en revalidant le type
(voir plus bas).

Sinon l'origine repasse à `'classified'` (un ré-import après #1742 qui reconnaît
désormais le sport efface le marquage). `'manual'` n'est jamais réécrit.

Le calcul est un geste de lot (les splits se lisent sur tous les résultats de
l'épreuve), à placer dans `import_persistence` **après** la persistance, sur les
épreuves finales du lot : il suit donc naturellement un reclassement ou une
création, sans toucher `reclassify` ni `get_or_create_course`. La protection des
épreuves `manual` contre le reclassement vient de #1745, on ne la réimplémente
pas.

Un faux positif se sort de la liste en enregistrant le type depuis l'écran
admin, même inchangé : `update_course` passe alors l'origine à `'manual'`
(aujourd'hui il ne fait rien quand aucun champ ne change).

### Épreuves déjà en base

Décidé par l'utilisateur : une migration de données pose `'fallback'` sur les
épreuves existantes qui répondent aux trois critères (splits lus en base sur les
participations, même prédicat que l'import). Sans elle, la liste resterait vide
jusqu'au prochain ré-import de chaque épreuve. Attendu en prod : 16 épreuves
(25 moins les Cyclathlon si #1742 les a reclassées avant).

### Liste admin (décidé par l'utilisateur)

- API : un filtre booléen sur la liste admin des épreuves (le endpoint qui
  alimente `/admin/courses`), et `event_type_origin` exposé dans son schéma de
  sortie.
- Front `/admin/courses` : une case « Type à vérifier » dans les filtres
  existants (lue depuis l'URL comme les autres, `page.tsx`), et un badge
  « Type à vérifier » sur la ligne marquée. La correction du type se fait déjà
  depuis cet écran.

### Tests

- Un nom sans sport et sans splits multisport (un nom neutre comme
  `La Chaussaire - Solo`) est marqué.
- `Triathlon M de X` n'est pas marqué ; un heat `Format S` sous un événement
  triathlon (nom `Triathlon L de Mimizan - Format S`) non plus.
- Un nom neutre dont les résultats portent natation et vélo n'est pas marqué.
- Une épreuve `manual` n'est jamais remarquée ; une correction admin la sort du
  filtre.
- Le filtre API et le badge front.

## Contraintes

- Chaîne Alembic unique : #1745 (colonne, sur `c38bc1342485`) → #1743 (entrée de
  portée) → #1744 (rattrapage éventuel). Rebase sur la tête du moment avant PR.
- Couches `api → services → repositories → DB`.
- TDD.

## Laissé au builder

Emplacement exact du calcul dans `import_persistence`, nom de la fonction publique
du classifieur, forme exacte du filtre (`?type_a_verifier=1` ou autre, en suivant
les filtres existants de l'écran).

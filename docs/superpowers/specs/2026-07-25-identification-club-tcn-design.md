# Identification du club TCN et disciplines hors fédération

Issue : [#76](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/76)
Date : 2026-07-25

## Problème

Est aujourd'hui considéré comme membre du TCN **tout coureur dont le libellé de
club contient « nantais »**. Le front force `club = "nantais"`
(`frontend/lib/club-constants.ts:5`), le backend en fait un `ILIKE '%nantais%'`
sur `Participation.club` (`app/core/club.py:11`, appliqué en
`app/repositories/participation_repository.py:117`).

Sur la course 15 (Naoned Urban Trail 2026, Breizh Chrono), 15 participations
sont retenues comme TCN, **2 seulement le sont** :

| Libellé club | Participations | TCN ? |
|---|---:|:--:|
| ASSOCIATION SPORTIVE  MARATHONIENS NANTAIS | 6 | ✗ |
| S/L STADE NANTAIS AC | 5 | ✗ |
| RACING CLUB NANTAIS * | 2 | ✗ |
| TRIATHLON CLUB NANTAIS | 2 | ✓ |

À l'échelle de la base, 13 faux positifs sur 249 participations comptées comme
club (5,2 %), tous issus de cette épreuve. Ils polluent le dashboard, la page
club et les compteurs de #77.

Le double espace de « ASSOCIATION SPORTIVE  MARATHONIENS NANTAIS » n'est pas une
coquille de ce document : il est dans la donnée, et sert de cas de test réel à
la normalisation.

## Trois définitions concurrentes

Le prédicat « appartient au TCN » existe en trois exemplaires divergents. C'est
la cause structurelle : la plus permissive des trois fait autorité sur les
compteurs.

| Emplacement | Liste | Usage |
|---|---|---|
| `backend/app/core/club.py:11` | `nantais`, `tcn`, `triathlon club nant` | filtre SQL des compteurs |
| `frontend/lib/utils/club.ts:1` | idem, réécrite en TS | badges, compteur d'épreuve |
| `backend/app/scrapers/klikego.py:303` | + `tri club nant` | splits fins Breizh Chrono |

Mesure annexe : **aucune** participation ne porte « TCN » sans contenir
« nantais » ; ce mot-clé ne sert à rien aujourd'hui. À l'inverse, 84
participations portent « TRI CLUB NANTAIS » et ne matchent *que* par « nantais ».
Remplacer naïvement « nantais » par les deux autres mots-clés ferait donc perdre
un tiers des vraies participations club.

## Le caractère FFTRI n'est pas la cause

L'issue propose de bloquer l'import des épreuves non-FFTRI. Cela masquerait le
symptôme sur la course 15, mais un club nantais non-TCN engagé sur un triathlon
fédéral serait compté de la même façon. Les deux sujets sont traités ici, dans
cet ordre de priorité : le filtre club est le bug, la discipline est une
pollution distincte des compteurs.

## Périmètre

Dans le périmètre :

- resserrement du prédicat club en une liste blanche, source unique backend ;
- exposition de `is_tcn` dans le DTO, suppression du prédicat frontend ;
- bascule du paramètre d'API `club` (texte libre) vers `scope` ;
- paramètre `federal_only` et toggle d'écran pour les disciplines hors fédération ;
- commande CLI de diagnostic des libellés club ;
- réutilisation du prédicat par le scraper Breizh Chrono.

Hors périmètre :

- **repli sur `Athlete.club` quand `Participation.club` est vide** (cas constaté
  sur Carnac 2025, colonne club absente à la source). Réserve légitime, mais
  sans régression ici : un club vide ne matchait déjà rien avant. Sujet séparé.
- **plafond `page_size` à 5000** sur `/participations`, atteint sans signal par
  le dashboard. Risque à horizon lointain (249 participations club aujourd'hui),
  pas un problème actuel.
- **nettoyage de données** : les faux positifs sont calculés à la requête, pas
  stockés. Ils disparaissent sans migration ni re-scrape.

## Décision 1 — liste blanche normalisée

`app/core/club.py` devient l'unique définition :

```python
TCN_CLUB_LABELS = frozenset({"triathlon club nantais", "tri club nantais", "tcn"})

def normalize_club(club: str | None) -> str: ...   # minuscules, bords et espaces internes aplatis
def is_tcn(club: str | None) -> bool: ...          # normalize_club(club) in TCN_CLUB_LABELS
def tcn_clause(column): ...                        # la même chose, en SQLAlchemy
```

Match à l'**égalité** sur la forme normalisée, plus en sous-chaîne :
« RACING CLUB NANTAIS * » se normalise en `racing club nantais`, absent de la
liste, exclu. « TRI CLUB NANTAIS » est retenu. Sur les données de prod du
25/07/2026 : 236 vraies participations, 0 faux positif.

Le mot-clé `tcn` est conservé bien qu'il ne matche rien aujourd'hui : en égalité
stricte il ne peut plus rien attraper d'indésirable.

`TCN_KEYWORDS` et `club_keyword_filter` disparaissent — la recherche par
sous-chaîne libre n'est utilisée par aucun appelant (cf. décision 2).

### Le prédicat vit deux fois, et c'est assumé

Il faut une version Python (champ `is_tcn` du DTO, scraper) **et** une version
SQL (filtrer et paginer sans charger toute la table). `tcn_clause` reproduit la
normalisation en SQL : `lower` + `trim` + trois `replace` imbriqués pour aplatir
les espaces internes — portable SQLite et Postgres, couvre jusqu'à huit espaces
consécutifs ; au-delà le libellé sort du filtre, ce qui ne peut produire qu'un
oubli, jamais un faux positif.

La garantie de non-divergence est un **test paramétré partagé** : le même jeu de
libellés (les 6 de la table ci-dessus, plus casse mixte, vide, `None`, ville
« NANTES (44200) », espaces multiples) passe dans `is_tcn()` et dans une requête
filtrée par `tcn_clause`, et les deux verdicts doivent coïncider. Une dérive
future devient un échec de test, pas un écart silencieux entre le badge affiché
et le compteur.

## Décision 2 — le paramètre `club` devient `scope`

`club` est déclaré comme un texte libre cherché en sous-chaîne, avec un séparateur
`|` pour cumuler des mots-clés. Le front n'y envoie jamais que `"nantais"`, sur
tous les endpoints. Cette souplesse n'est utilisée par personne, et c'est elle
qui a laissé le bug s'installer : elle place la définition du club **chez
l'appelant**.

`club: str | None` est donc retiré au profit de `scope: str | None`, dont la
seule valeur reconnue est `"club"`. Endpoints concernés : `/participations`,
`/courses`, `/courses/events`, `/athletes`, `/stats`, `/stats/seasons`,
`/stats/events-geo`.

C'est une **rupture de contrat sur `/api/v1`, assumée** : le seul consommateur
est notre front, déployé de pair. Pas d'alias déprécié, pas de chemin mort à
nettoyer plus tard.

Le front parle déjà ce vocabulaire (`lib/scope.ts`, `SCOPE_PARAM`,
`ScopeToggle`) : `TCN_CLUB_FILTER` et `clubFromScope` disparaissent, le paramètre
d'URL `?scope=club` est relayé tel quel à l'API.

Côté `athlete_repository.search`, le filtre porte sur `Athlete.club` : `scope`
y applique `tcn_clause(Athlete.club)`.

## Décision 3 — `is_tcn` dans le DTO, prédicat frontend supprimé

`ParticipationOut` gagne `is_tcn: bool`, calculé depuis `Participation.club`.
`frontend/lib/utils/club.ts` et son test sont supprimés ; `courses/[id]/page.tsx`
(badge + compteur d'épreuve), `RaceFinishers.tsx` (badge + filtre local) et
`Leaderboard.tsx` lisent `p.is_tcn`.

Le front ne peut plus diverger du backend : il n'a plus d'opinion.

Un cas demande une adaptation : la carte « Top clubs » de `courses/[id]` agrège
les participations **par libellé de club** et surligne la ligne du TCN
(`isTCN(name)`, ligne 143). Le drapeau n'y porte pas sur une participation mais
sur un groupe. Il se dérive sans prédicat local : à la construction du
regroupement, chaque libellé hérite du `is_tcn` de l'une quelconque de ses
participations — elles portent toutes le même, puisque le drapeau est fonction
du libellé seul.

## Décision 4 — disciplines hors fédération

Le classifieur produit déjà la donnée : la course 15 est `event_type: "trail"`.

Est **fédérale** une course dont la base de sport n'est pas dans
`{trail, course-a-pied, cyclisme}`. Liste d'**exclusion** délibérée : une
discipline future est fédérale par défaut, ce qui prolonge le repli du
classifieur (`classify.py:151`, tout texte non reconnu retombe sur `triathlon`).
La constante vit dans `app/scrapers/classify.py`, aux côtés de `BARE_TYPES`, et
s'appuie sur `_sport_base` déjà présent dans `services/mapping.py:44`.

Nouveau paramètre `federal_only: bool = False` sur les mêmes endpoints que
`scope`, threadé exactement comme l'est déjà `seasons` : router → service →
`_apply_filters` / `for_stats` / `_grouped_events_query` / `events_with_counts`
/ `list_seasons`. Le précédent `seasons` sert de patron, y compris pour les
tests.

**L'API reste neutre par défaut.** Le « exclues par défaut » est un défaut
d'**écran**, pas d'API : dashboard et page club envoient `federal_only=true`, la
page Résultats ne l'envoie pas. Un défaut à `true` côté API amputerait
silencieusement les données de tout futur appelant — exactement le travers que
cette issue corrige.

Toggle « Inclure les autres disciplines » sur le dashboard et la page club, en
paramètre d'URL comme `scope`, à côté du `ScopeToggle` existant.

Effet cumulé attendu sur les compteurs du dashboard (mesuré sur la prod du
25/07/2026, via `/api/v1/participations?club=nantais&page_size=5000`) :

| | Participations | Athlètes | Épreuves |
|---|---:|---:|---:|
| Aujourd'hui | 249 | 182 | 12 |
| Après le filtre club (décision 1) | 236 | 169 | 12 |
| Après `federal_only` (décision 4) | 234 | 168 | 11 |

L'épreuve reste au compteur après la décision 1 — la course 15 porte deux vrais
membres — et n'en sort qu'avec `federal_only`. Les deux décisions retirent donc
bien deux choses différentes.

## Décision 5 — commande CLI de diagnostic

L'égalité stricte a un défaut connu : une variante non répertoriée
(« TCN TRIATHLON », « T.C.N. ») fait disparaître un membre des compteurs **sans
aucun signal**. C'est le travers que la CLI proscrit ailleurs (« No silent
caps »).

```
$ uv run python -m app.cli club-labels --like nant

  236  ✓  TRIATHLON CLUB NANTAIS
   84  ✓  TRI CLUB NANTAIS
    6  ✗  ASSOCIATION SPORTIVE MARATHONIENS NANTAIS
    5  ✗  S/L STADE NANTAIS AC
    2  ✗  RACING CLUB NANTAIS *
    1  ✗  NANTES (44200)
```

Libellés club distincts, triés par nombre de participations décroissant, marqués
reconnus ou non. `--like` filtre sur une sous-chaîne (défaut : tous les
libellés). `--json` bascule le rapport texte sur stderr et ne laisse que la ligne
JSON sur stdout, comme les deux autres commandes.

Couche mince conforme à `app/cli/` : la commande vit dans
`app/cli/commands/club_labels.py`, l'agrégation dans le repository (`SELECT club,
count(*) GROUP BY club`), le rendu dans `cli/reports.py`.

## Décision 6 — le scraper Breizh Chrono réutilise le prédicat

`_fetch_tcn_fine_splits` (`app/scrapers/breizhchrono.py:267`) importe
`_TCN_KEYWORDS` de `klikego.py` pour décider à qui aller chercher les splits
fins. Cette liste est supprimée au profit de `core.club.is_tcn`.

Ici, la permissivité ne coûtait qu'en requêtes HTTP inutiles, pas en exactitude.
Le resserrement est donc un gain accessoire : sur la course 15, 13 appels
`resultat-participant.jsp` de moins.

Le sens de la dépendance mérite un mot : un scraper qui importe
`app.core.club` reste conforme à l'architecture en couches (`core` est la base,
tout le monde en dépend) ; c'est l'import croisé `breizhchrono → klikego._TCN_KEYWORDS`
qui était le contournement.

## Tests

Sans réseau, comme le reste de la suite unitaire.

**`tests/test_core/test_club.py`** — le prédicat : les 3 vrais libellés dans
leurs casses observées, les 3 faux positifs de l'issue, une ville
(« NANTES (44200) »), vide, `None`, espaces multiples.

**`tests/test_repositories/test_club_filter.py`** — le test paramétré partagé
Python ≡ SQL décrit en décision 1. C'est le test qui verrouille l'invariant ;
il doit échouer si l'une des deux implémentations bouge seule.

**`tests/test_api/`** — `scope=club` filtre bien (régression directe de #76 : une
épreuve peuplée des 6 libellés ne doit rendre que les 3 vrais) ; `is_tcn` présent
et correct dans la réponse ; `federal_only` exclut trail / course-à-pied /
cyclisme et conserve triathlon, duathlon, swimrun, aquathlon, aquarun, bike-run ;
absence de `federal_only` = aucun filtrage.

**`tests/test_cli/test_club_labels.py`** — sortie texte, `--like`, `--json`
(stdout ne contient que la ligne JSON).

**Frontend (Vitest)** — les badges et compteurs lisent `is_tcn` ; le toggle
disciplines écrit et lit son paramètre d'URL. Les tests existants de
`lib/utils/club.test.ts` sont supprimés avec le module ; ceux de
`lib/scope.test.ts` et `dashboard/page.test.tsx` sont adaptés à `scope`.

## Vérification de bout en bout

Après déploiement, la course 15 doit afficher **2** participants TCN au lieu de
15, et le dashboard **234** participations club au lieu de 249 — toggle
« Inclure les autres disciplines » décoché ; coché, 236.

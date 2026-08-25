# Phase 1 — Modèle de données : la page épreuve (lot #486)

**Aucune table, aucune colonne, aucune migration Alembic.** Ce lot ne persiste rien : il
publie quatre agrégats calculés à la lecture, et deux règles de sélection. Le modèle
normalisé (`Athlete`, `Course`, `Participation`) est inchangé.

---

## 1. Les quatre champs publiés

### `CourseSummary.clubs_total: int`

Nombre de clubs **distincts** renseignés sur l'épreuve entière.

- **Dénominateur de** : le pied « et N autres clubs », où `N = clubs_total − len(clubs)`.
- **Attention au faux ami** : `categories_total`, voisin dans le même DTO, compte des
  **participants** (« somme sur toutes les catégories »). `clubs_total` compte des
  **clubs**. Les deux servent le même besoin — dire ce que la carte omet — mais ne sont
  pas homogènes, et la docstring doit le dire, sans quoi le prochain lecteur en déduira
  une symétrie qui n'existe pas.
- **Vaut 0** quand aucun participant ne porte de club. La carte rend alors son état
  d'absence, sans en-tête de colonnes (`FR-016`).
- **Source** : `len(clubs_counter)` dans `stats_service.course_summary`, où le `Counter`
  est déjà construit. Coût marginal nul.

### `CourseSummary.split_gap_median: float | None`

Médiane des écarts relatifs `(total − Σ inters) / total` sur les lignes **évaluables** de
l'épreuve (définition en § 2).

- **Nul** quand l'épreuve ne compte aucune ligne évaluable — relais, épreuve sans splits,
  ou schéma de segments jamais complet. C'est le cas le plus fréquent : sur la base de dev,
  25 épreuves sur 72 seulement ont des lignes évaluables.
- **Sert deux fois** : de seuil au signal d'épreuve (`|médiane| > 1 %` → « les inters
  publiés ne couvrent pas tout le parcours »), et de **référence** au marqueur de ligne.
- **Reste une mesure brute** : le serveur publie la médiane, jamais le verdict. Les seuils
  d'affichage (1 %, 5 %) vivent côté écran — ce qui permet de les régler après re-sondage
  sur la base de production sans toucher au contrat.

### `ParticipationOut.split_gap_ratio: float | None`

Écart relatif signé de **cette** ligne : `(total − Σ inters) / total`.

- **Nul** quand la ligne n'est pas évaluable (§ 2). C'est le cas majoritaire : 4 150 lignes
  évaluables sur 11 629.
- **Signé, pas absolu** : le signe porte l'information. Un écart positif dit « le total
  couvre plus que la somme des inters » — un segment non publié. Un écart négatif dit
  l'inverse, ce qui n'a pas d'explication bénigne. 81,7 % des écarts mesurés sont positifs.
- **Publié plutôt que recalculé côté écran** : c'est le cœur de R2. Le front en a besoin
  par ligne, le back en a besoin pour la médiane ; l'implémenter deux fois, c'est #76.

### `EventOut.is_reliable: bool | None` et `EventOut.quality_issues: dict[str, int] | None`

Miroir exact des deux champs déjà portés par `CourseBrief`, pour que la liste des épreuves
puisse marquer ce qu'elle liste sans un second appel.

- **`is_reliable` est un `hybrid_property`** de `Course`
  (`coalesce(reliability_override, is_reliable_computed)`) : son expression SQL est
  utilisable telle quelle dans le `SELECT` agrégé.
- **`quality_issues` est une colonne `JSON`** et ne doit **pas** entrer dans le `GROUP BY` :
  PostgreSQL n'a pas d'opérateur d'égalité sur `json`, la requête passerait en SQLite et
  échouerait en production. La requête groupant déjà par `Course.id`, la dépendance
  fonctionnelle suffit — les cinq colonnes déjà listées dans le `GROUP BY` y sont
  d'ailleurs redondantes pour la même raison.
- **`None` des deux côtés** est un état normal : les imports antérieurs au calcul de
  fiabilité ont été laissés tels quels. `EventsTable` du profil athlète a déjà le repli à
  réutiliser (« Fiabilité des données incertaine chez le chronométreur… »).

---

## 2. La règle d'écart, et son domicile unique

Elle vit dans `backend/app/services/split_gap.py`, et **nulle part ailleurs**.

### Ce qui rend une ligne évaluable

Les cinq conditions sont **cumulatives**. Une seule qui manque, et `split_gap_ratio` vaut
`None` — le produit ne signale que ce qu'il a mesuré (`FR-010`).

1. L'épreuve **n'est pas un relais** : la somme des inters d'un relayeur ne se compare pas
   à son temps.
2. La ligne **porte des splits**.
3. Le **schéma de segments du sport est complet** dans cette ligne — chacune de ses clés
   présente. Les schémas sont ceux de l'écran : triathlon `swim/t1/bike/t2/run`, duathlon
   `course1/t1/bike/t2/course2`, aquathlon `swim/run`, aquarun `swim/t1/run`, bike-run
   `bike/run`.
4. Le **temps total est lisible** comme une durée, et non nul.
5. **Chaque inter du schéma est lisible** comme une durée.

Sur 11 629 lignes de la base de dev : 3 254 tombent sur (3), 3 123 sur (2), 1 041 sur (1),
37 sur (4), 24 sur (5) — et 4 150 sont évaluables.

### Les deux seuils d'affichage

Ils vivent côté écran, pas dans le contrat.

| Signal | Condition | Mesuré sur la base de dev |
| --- | --- | --- |
| **Épreuve** — « les inters publiés ne couvrent pas tout le parcours » | `|split_gap_median| > 1 %` | 5 épreuves sur 25 |
| **Ligne** — marqueur discret | `|ratio − médiane| > 5 %` **et** l'épreuve compte ≥ 10 lignes évaluables **et** l'écart vaut ≥ 60 s en valeur absolue | **0 ligne sur 4 150** |

Les deux gardes du signal de ligne ne sont pas décoratives : sans le seuil d'effectif, une
épreuve de neuf enfants aux totaux de cinq minutes fait signaler deux lignes pour vingt
secondes ; sans le plancher en secondes, un petit dénominateur suffit à franchir 5 %.

**Le seuil de 2 % de l'audit est écarté** : mesuré, il signalait 333 lignes (8,02 %), dont
285 sur une épreuve que le produit tient pour fiable. Détail et alternatives dans
`docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`, qui prime sur ce
document.

### Ce que la règle ne prouve pas encore

Zéro ligne signalée sur la base de dev établit l'absence de bruit, **pas** la captation :
la base ne contient aucune ligne fausse au sens de `RES-10`. Le cas de l'audit — course
214, 31 s + 34 s + 19 min 18 s pour 1 h 06 min 18 s, soit 69,3 % — doit être figé en
fixture de test, faute de quoi la règle pourrait cesser de capter sans que rien le dise.

---

## 3. La sélection du classement

Quatre restrictions, cumulables, toutes portées par l'URL de l'écran et par les paramètres
de `GET /courses/{course_id}`.

| Restriction | Paramètre | Existant ? | Comparaison |
| --- | --- | --- | --- |
| Recherche par nom | `q` | oui | partielle, nom ou prénom |
| Portée club TCN | `scope=club` | oui | `app/core/club.py`, dépositaire unique (#76) |
| **Club** | `club` | **nouveau** | **égalité exacte** sur `Participation.club` |
| **Catégorie** | `category` | **nouveau** | **égalité exacte** sur `Participation.category` |

**Pourquoi l'égalité exacte** : les valeurs proposées à l'écran sont littéralement les
chaînes stockées — elles viennent d'un `Counter` sur ces deux colonnes. Une comparaison
partielle ferait diverger le compteur affiché sur la carte du total rendu par le
classement, ce qui est précisément le défaut que `RES-9` vient de faire corriger par le
lot #485.

**Défaut neutre** (`None` = pas de filtre), Principe V. Aucune combinaison n'est interdite
côté API : c'est l'écran qui rend lisible le cas « club ≠ TCN **et** portée TCN », vide par
construction.

**Cardinalité mesurée** : 1 393 clubs distincts et 123 codes de catégorie distincts sur la
base de dev — assez pour que ces filtres aient un sens, trop pour en faire des énumérations
fermées côté contrat.

---

## 4. La table des libellés de catégorie

`frontend/lib/categories.ts`, nouvelle, **côté écran seulement** : c'est un libellé
d'affichage, il ne conditionne aucune requête, et le mettre en base ferait une migration
pour une constante.

**Structure** : une table de codes de base, plus des règles de dérivation.

- 17 codes de base (`PO`, `PU`, `BE`, `MI`, `CA`, `JU`, `SE`, `S1`…`S4`, `V1`…`V6`) ;
- une **règle de suffixe de genre** — `S2M`, `S2H`, `S2F` dérivent de `S2` ;
- une **règle de genre en mot préfixe** — `M SENIOR`, `F VETERAN` ;
- les séries masters étrangères à la FFTRI — `M0`…`M6`, `MA1`…`MA5`.

**Couverture mesurée** : la table de base et la seule règle de suffixe couvrent déjà
**80,7 % des lignes** (61 codes sur 123). Les deux règles suivantes ajoutent environ 13
points. Le relevé exact des codes à inscrire est une requête sur la base, pas un
arbitrage — il se fait au moment d'écrire la table.

**Un code hors table s'affiche tel quel** (`FR-029`). C'est la seule réponse honnête pour
une queue de 37 codes à 150 lignes, et le produit a déjà ce réflexe : `describeQualityIssues`
rend un code d'anomalie inconnu avec son compteur plutôt que de l'avaler.

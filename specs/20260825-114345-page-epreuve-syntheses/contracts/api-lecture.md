# Contrat — le delta sur l'API de lecture `/api/v1` (lot #486)

`/api/v1` est **publiée**, et le Principe IV de la constitution interdit de la modifier
silencieusement : un champ retiré, une sémantique inversée ou un code de retour changé
motivent une v2. Tout ce qui suit est **additif**, et se vérifie comme tel (`SC-010`).

---

## `GET /courses/{course_id}` — deux paramètres facultatifs

### Ajouts

| Paramètre | Type | Défaut | Sémantique |
| --- | --- | --- | --- |
| `club` | `str \| None` | `None` | Ne garde que les participants dont le club **vaut exactement** cette chaîne. |
| `category` | `str \| None` | `None` | Ne garde que les participants dont la catégorie **vaut exactement** cette chaîne. |

**Défaut neutre** (Principe V) : absents, ils ne filtrent rien, et la réponse est
identique octet pour octet à celle d'aujourd'hui.

**Cumul** : `club`, `category`, `q` et `scope` se composent par conjonction. Aucune
combinaison n'est refusée — `?club=BLAIN%20TRIATHLON&scope=club` rend légitimement un
classement vide, et c'est à l'écran de l'expliquer, pas à l'API de l'interdire.

**Effet sur `total`** : il porte sur la **sélection**, filtres compris — comportement
inchangé, `q` et `scope` le faisaient déjà. Les décomptes de l'épreuve entière restent dans
`GET /courses/{course_id}/summary`, qui n'accepte toujours aucun paramètre.

**Valeur inconnue** : une chaîne qui ne correspond à aucun participant rend
`participations: []` et `total: 0`. **Jamais** un 404 — l'épreuve existe, c'est la
sélection qui est vide.

### Exemple

```http
GET /api/v1/courses/214?club=BLAIN%20TRIATHLON&page=1&page_size=20
GET /api/v1/courses/214?category=V2
GET /api/v1/courses/214?category=V2&q=kermarrec&scope=club
```

### Réponse — un champ ajouté par participation

`ParticipationOut` gagne :

```jsonc
{
  "split_gap_ratio": 0.693   // float | null
}
```

Écart relatif **signé** entre le temps total et la somme des temps intermédiaires de cette
ligne : `(total − Σ inters) / total`. `null` quand la ligne n'est pas évaluable — relais,
splits absents, schéma de segments incomplet, total ou inter illisible (les cinq conditions
sont en § 2 de [`data-model.md`](../data-model.md)).

Le signe porte l'information : positif, le total couvre plus que la somme des inters (un
segment n'est pas publié) ; négatif, la somme dépasse le total, ce qui n'a pas
d'explication bénigne.

**C'est une mesure, pas un verdict.** L'API ne dit jamais « cette ligne est douteuse » :
elle publie l'écart, et les seuils d'affichage vivent côté écran. C'est ce qui permettra de
les régler après re-sondage sur la base de production sans toucher au contrat.

---

## `GET /courses/{course_id}/summary` — deux champs ajoutés

La route **n'accepte toujours aucun paramètre**, et c'est structurant : ses agrégats
portent sur l'épreuve entière, sans quoi chercher un nom ferait tomber l'histogramme à une
barre (#163). Les deux filtres ci-dessus ne l'atteignent pas.

```jsonc
{
  "clubs_total": 187,            // int
  "split_gap_median": 0.0169,    // float | null
  "split_gap_rows": 681          // int
}
```

**`clubs_total`** — nombre de clubs **distincts** renseignés sur l'épreuve. Dénominateur du
pied « et N autres clubs », avec `N = clubs_total − clubs.length`. Vaut `0` quand aucun
participant ne porte de club.

> ⚠️ Ce champ n'est **pas** homogène à son voisin `categories_total`, qui compte des
> **participants**. Les deux disent ce que la carte omet, mais dans deux unités
> différentes. La docstring du schéma doit le porter.

**`split_gap_median`** — médiane des `split_gap_ratio` non nuls de l'épreuve. `null` quand
l'épreuve ne compte aucune ligne évaluable, ce qui est le cas courant (25 épreuves sur 72
en ont sur la base de dev).

Elle sert de **référence** : un écart de ligne ne se juge pas dans l'absolu mais par
rapport à ses pairs, l'écart étant le plus souvent une propriété de l'épreuve — un segment
que le chronométreur ne publie pas — et non de la ligne.

**`split_gap_rows`** — nombre de lignes évaluables, celles sur lesquelles la médiane est
calculée. Ajouté à l'implémentation : sans lui, l'écran ne peut pas appliquer la garde
d'effectif du sondage, et la médiane d'une population de neuf se retrouverait traitée comme
une référence — c'est précisément le cas de la course 65, neuf enfants aux totaux de cinq
minutes, où vingt secondes font 6 %.

---

## `GET /courses/events` — deux champs ajoutés

`EventOut` gagne le miroir exact des deux champs déjà portés par `CourseBrief` :

```jsonc
{
  "is_reliable": false,                       // bool | null
  "quality_issues": { "duplicate_bib": 3 }    // {str: int} | null
}
```

`null` des deux côtés est un état normal — les imports antérieurs au calcul de fiabilité
n'ont pas été rétro-remplis, et l'écran a déjà son repli générique.

**Piège d'implémentation, pas de contrat** : `quality_issues` est une colonne `JSON` et ne
doit pas entrer dans le `GROUP BY` de la requête agrégée — PostgreSQL n'a pas d'opérateur
d'égalité sur `json`, et la requête passerait en SQLite pour échouer en production. Le
`GROUP BY Course.id` existant suffit par dépendance fonctionnelle.

---

## Ce qui ne change pas

- Aucun champ retiré, aucun renommé, aucune sémantique inversée.
- Aucun code de retour modifié : 404 reste réservé à l'épreuve inconnue.
- `page_size=all` reste atteignable et se combine aux nouveaux filtres.
- `GET /courses/{course_id}/summary` reste sans paramètre.
- Aucune migration Alembic : ces six champs sont calculés à la lecture.

## Vérification de l'additivité

`SC-010` se vérifie en rejouant les appels existants **sans** les nouveaux paramètres et en
comparant les réponses aux clés d'origine. Les tests d'API existants
(`backend/tests/test_api/`) portent déjà ces appels : ils doivent rester verts **sans
modification d'assertion** — c'est le critère, pas l'absence d'erreur.

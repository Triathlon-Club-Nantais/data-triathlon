# Contrat — API de lecture d'une épreuve

**Base** : `/api/v1` — pas de v2 (cf. `plan.md`, Constitution Check, Principe IV).

---

## `GET /courses/{course_id}`

Classement d'une épreuve, **paginé par défaut**. C'est un changement de
comportement de la route existante (FR-005) : elle rendait jusqu'ici
l'intégralité des participations.

### Paramètres

| Nom | Type | Défaut | Sens |
|---|---|---|---|
| `page` | `int ≥ 1` | `1` | tranche demandée |
| `page_size` | `int` (1–200) ou `all` | `20` | taille de tranche ; `all` rend tout en une page (FR-006) |
| `q` | `str` | absent | recherche sur le nom **ou** le prénom de l'athlète, en sous-chaîne, insensible à la casse et aux accents |
| `scope` | `club` | absent | restreint aux membres du TCN. Défaut neutre (Principe V) |

### Réponse `200`

```json
{
  "course": { "id": 25, "name": "…", "event_date": "2025-06-15", "event_type": "triathlon-m", "…": "…" },
  "participations": [ { "id": 1, "athlete": {}, "course": {}, "rank_overall": 1, "…": "…" } ],
  "total": 2517,
  "page": 1,
  "page_size": 20
}
```

- `course` — inchangé, un `CourseBrief`.
- `participations` — la tranche, dans l'ordre d'affichage (voir plus bas).
  **Nom de clé conservé** : `participations`, et non `items`, pour ne pas
  casser l'enveloppe existante plus que nécessaire.
- `total` — nombre de participations correspondant à `q` et `scope`, pas
  au nombre de partants. Le décompte d'épreuve vit dans la synthèse.
- `page_size` — `null` lorsque `all` a été demandé.

### Ordre des participations

Une seule définition, appliquée en base **avant** le découpage :

1. finishers d'abord, puis `DNF`, puis `DSQ`, puis `DNS` ;
2. dans les finishers : rang croissant, les non classés en fin ;
3. dans les autres groupes : temps croissant, les temps absents en fin ;
4. à égalité : nom puis prénom.

Un `total_time` vide ou égal à `00:00:00` vaut temps absent.

### Erreurs

| Code | Cas |
|---|---|
| `404` | épreuve inexistante — inchangé |
| `422` | `page < 1`, `page_size` hors de 1–200, ou `page_size` ni entier ni `all` |

Un `page` au-delà du dernier n'est **pas** une erreur : `participations` est
vide et `total` reste exact (FR-004).

---

## `GET /courses/{course_id}/summary`

Synthèse d'une épreuve **entière**. Route nouvelle, aucune régression possible.

### Paramètres

Aucun. Ni `q`, ni `scope`, ni pagination : la synthèse ne dépend d'aucune
sélection (FR-018). C'est délibéré et non une omission — chercher un nom ne doit
pas faire tomber l'histogramme à une barre.

### Réponse `200`

```json
{
  "total": 2517,
  "finishers": 2380,
  "non_finishers": 112,
  "unknown": 25,
  "tcn_count": 14,
  "male": 1980,
  "female": 490,
  "categories": [ { "name": "SEM", "count": 402 } ],
  "clubs": [ { "name": "TRIATHLON CLUB NANTAIS", "count": 14, "is_tcn": true } ],
  "histogram": { "bars": [3, 18, 47], "start_sec": 7200, "bucket_sec": 300 },
  "split_keys": ["swim", "t1", "bike", "t2", "run"]
}
```

- `total = finishers + non_finishers + unknown`, invariant éprouvé par un test.
- `male` + `female` ne somment pas nécessairement à `total` : les lignes sans
  genre lisible ne sont comptées ni d'un côté ni de l'autre. Plusieurs sources
  ne publient pas le genre (`gender: "U"` sur 41 % des lignes Sporthive).
- `categories` — 8 au plus, décroissant. `clubs` — 9 au plus, décroissant.
  Mêmes limites qu'aujourd'hui côté navigateur.
- `histogram` — `null` si aucun temps exploitable. `bars` est plafonné à 60
  tranches, `bucket_sec` vaut 300.
- `split_keys` — les clés renseignées sur au moins une participation, dans
  l'ordre d'apparition. C'est cette liste, et non les lignes de la page
  courante, qui fixe les colonnes du tableau (FR-028).
- `is_tcn` vient de `core/club.is_tcn` et de nulle part ailleurs (#76).

### Cas limite

Épreuve sans participation : `200` avec tous les compteurs à zéro, listes vides
et `histogram: null`. Jamais une erreur (FR-021).

### Erreurs

| Code | Cas |
|---|---|
| `404` | épreuve inexistante |

---

## Contrat d'interface — page `/courses/{id}`

Trois paramètres d'URL, tous facultatifs :

| Paramètre | Valeurs | Défaut |
|---|---|---|
| `page` | entier ≥ 1 | `1` |
| `q` | texte libre | absent |
| `scope` | `club` | absent |

`scope` réutilise `SCOPE_PARAM` / `SCOPE_CLUB` de `lib/scope.ts` — le paramètre
qui pilote déjà la portée club sur le tableau de bord et la page club.

Règles :

- toute modification de `q` ou de `scope` remet `page` à 1 (FR-025) ;
- un `page` absent, non numérique ou < 1 est traité comme 1, sans erreur ;
- les contrôles de pagination sont des liens (`<Link>`), donc ouvrables en
  nouvel onglet et utilisables avant hydratation (FR-026) ;
- aucun contrôle de pagination n'est rendu quand la sélection tient en une page
  (FR-027).

# Data model : une identité stable par athlète réel (#1146)

Décisions et justifications : `research.md` (R1 à R9). Identifiants techniques en anglais (Principe I) ; `nom`/`prenom` existants inchangés.

## `athletes` (modifiée)

| Colonne | Type | Règle |
| --- | --- | --- |
| `last_name_key` | `String`, nullable | `identity_key(nom)` ; si le nom est vide et le prénom non, `identity_key(prenom)` (prénom seul = nom complet, cas Klikego) ; NULL si les deux sont vides |
| `first_name_key` | `String`, nullable | `identity_key(prenom)` ; `""` si prénom vide et nom non vide ; NULL si `last_name_key` est NULL |
| `homonym_rank` | `Integer`, NOT NULL, défaut 0 | 0 = fiche principale, ≥ 1 = homonyme distingué |

- **Contrainte** `uq_athlete_identity UNIQUE(last_name_key, first_name_key, homonym_rank)`, remplace `UNIQUE(nom, prenom, birth_date)`.
- **Index supprimé** : `ix_athletes_identity(lower(nom), lower(prenom))`.
- **Index ajoutés** (repli R4, déclarés pour les deux moteurs) : expression `last_name_key || first_name_key` et `first_name_key || last_name_key`.
- **Invariants** :
  - les deux clés sont écrites par le repository à chaque création ou renommage, jamais par l'appelant ;
  - `birth_date` ne participe plus à l'identité ;
  - l'import ne résout que vers `homonym_rank = 0`.

`identity_key(text)` (`app/core/athlete_identity.py`) : NFKD, retrait des marques combinantes, `casefold`, `œ→oe`, `æ→ae`, `ø→o`, `ł→l`, `đ→d`, puis caractères alphanumériques Unicode seuls (`str.isalnum`). Exemples : `Léo`→`leo`, `L'APPARTIEN`→`lappartien`, `LE GLOANIC`→`legloanic`, `Jean-marie`→`jeanmarie`, `CIC 7`→`cic7`, `Иванов`→`иванов`, `?`→`""`, `-`→`""`.

## `participations` (modifiée)

| Colonne | Type | Règle |
| --- | --- | --- |
| `athlete_locked` | `Boolean`, NOT NULL, défaut faux | posé par `reassign_participation` ; une ligne appariée par dossard n'est alors que mise à jour |
| `source_identity_key` | `String`, nullable | `"<last_name_key>\|<first_name_key>"` de la ligne source ; écrite par l'import à chaque création et mise à jour ; clé du multiset sans dossard |

Rétro-remplissage par la migration : `source_identity_key` = clé de la fiche actuelle. Pas d'index : `_index_course` charge déjà les participations de l'épreuve en une fois.

## `athlete_aliases` (nouvelle)

| Colonne | Type | Règle |
| --- | --- | --- |
| `id` | PK | |
| `last_name_key` | `String`, NOT NULL | |
| `first_name_key` | `String`, NOT NULL | |
| `athlete_id` | FK `athletes.id` ON DELETE CASCADE, indexé | fiche conservée |
| `created_at` | `DateTime(tz)` | |

- **Contrainte** `uq_athlete_alias UNIQUE(last_name_key, first_name_key)` : une variante n'appartient qu'à une fiche (FR-021b).
- **Écrite** par la fusion (clé de l'absorbée si elle diffère de la conservée ; variantes de l'absorbée repointées). Jamais par l'import.

## `ignored_athlete_pairs` (nouvelle)

| Colonne | Type | Règle |
| --- | --- | --- |
| `athlete_id_low` | FK `athletes.id` ON DELETE CASCADE | `min(a, b)` |
| `athlete_id_high` | FK `athletes.id` ON DELETE CASCADE | `max(a, b)` |
| `ignored_by_user_id` | FK `users.id` | |
| `ignored_at` | `DateTime(tz)` | |

Contrainte `UNIQUE(athlete_id_low, athlete_id_high)`. Une paire écartée ne revient plus en revue. Modèle : `ignored_course_duplicate`.

## Références déplacées par une fusion

| Table | Traitement |
| --- | --- |
| `participations.athlete_id` | repointé |
| `participation_teammates.athlete_id` | repointé ; refus si les deux fiches sont sur la même participation |
| `volunteer_actions.athlete_id` | repointé (plusieurs lignes par saison admises) |
| `season_validations.athlete_id` | repointé ; saison validée des deux côtés : la ligne de la conservée reste, l'autre est supprimée |
| `users.athlete_id` | repointé ; refus si les deux fiches sont liées à deux comptes différents |
| `athlete_aliases.athlete_id` | repointé, puis ajout de la clé de l'absorbée |
| `ignored_athlete_pairs` | lignes de l'absorbée supprimées par cascade |

Champs de la fiche conservée complétés depuis l'absorbée quand ils sont vides : `club` (+ `club_locked`), `gender`, `birth_date`. Deux `birth_date` différentes : refus.

## Transitions

```text
import (clé neuve)                    → fiche principale (rang 0)
import (dossard neuf, fiche déjà sur
        l'épreuve avec un autre dossard) → homonyme distingué (rang max+1)
fusion(conservée, absorbée)           → absorbée supprimée, variante ajoutée ;
                                        conservée passe au rang 0 si la
                                        principale de sa clé était l'absorbée
reassign_participation                → participation.athlete_locked = vrai
reprise, renormalisation              → fiche renommée, ou fusionnée dans la
                                        fiche cible existante
```

## Migrations (ordre des PR, `tasks.md`)

1. PR 1 : colonnes `last_name_key`, `first_name_key`, `homonym_rank` ; rétro-remplissage en Python (règle figée dans la migration), rangs par `id` croissant par groupe ; remplacement de `uq_athlete_identity` ; suppression de `ix_athletes_identity` ; index de concaténation. Downgrade : recrée l'ancienne contrainte après contrôle `GROUP BY … HAVING count(*) > 1` (modèle `b2c3d4e5f6a7`).
2. PR 2 : `participations.athlete_locked`, `participations.source_identity_key` (rétro-remplie).
3. PR 5 : tables `athlete_aliases`, `ignored_athlete_pairs`.

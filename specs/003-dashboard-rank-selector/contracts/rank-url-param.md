# Contract — Paramètre URL `?rank=`

**Feature** : `feat/104-dashboard-rank-selector`
**Nature** : contrat client (URL de page), pas d'API backend nouvelle.

Ce contrat définit la surface publique du paramètre `?rank=` tel qu'exposé aux utilisateurs et aux liens partagés. Il est stable ; tout changement de sémantique passe par une nouvelle valeur, pas une réinterprétation d'une valeur existante.

## Portée

- **Pages concernées** : `/dashboard`, `/club`.
- **Pages non concernées** (le paramètre est ignoré s'il apparaît dans leur URL, aucun crash) : toutes les autres — `/athletes/[id]`, `/courses/[id]`, `/resultats`, `/ajouter`, `/carte`, `/admin`, `/`.

## Valeurs autorisées

| Valeur d'URL | Sémantique | Rendu des cartes |
|---|---|---|
| `?rank=scratch` | Compte sur `rank_overall` seul | 3 cartes scalaires ; libellé secondaire : « scratch » |
| `?rank=category` | Compte sur `rank_category` seul | 3 cartes scalaires ; libellé : « catégorie » |
| `?rank=gender` | Compte sur `rank_gender`, ventilé F/H selon `athlete.gender` | 3 cartes dédoublées (F et H côte à côte dans la même carte, ou en deux valeurs distinctes) ; libellé : « genre — femmes / hommes » |
| `?rank=all` | Compte sur `min(rank_overall, rank_gender, rank_category)` | 3 cartes scalaires ; libellé : « scratch, genre ou catégorie » |

## Défaut et valeurs invalides

- **Absence du paramètre** (URL sans `?rank=`) → `scratch`.
- **Chaîne vide** (`?rank=`) → `scratch`.
- **Valeur inconnue** (`?rank=foo`, `?rank=women`, `?rank=CATEGORY`, casse non canonique) → `scratch`. **Silencieux** : ni redirection, ni erreur, ni redirection HTTP.

Contrat de silence : les URLs invalides ne cassent jamais la page. Un utilisateur qui tape n'importe quoi voit toujours quelque chose de sensé.

## Composition avec les autres paramètres

Le paramètre `?rank=` **compose** avec les autres paramètres de filtrage existants sans les remplacer. Toutes les combinaisons ci-dessous sont valides et se comportent comme l'intersection des filtres :

```text
/dashboard?rank=scratch
/dashboard?rank=category&seasons=2025-2026
/dashboard?rank=gender&sports=all
/club?rank=all&seasons=2024-2025,2025-2026
```

Aucun paramètre n'invalide ni ne réinitialise un autre. L'ordre des paramètres dans l'URL est indifférent.

## Persistance et partage

- **Le paramètre vit uniquement dans l'URL** — pas de localStorage, pas de cookie, pas de session serveur. Un lien copié-collé rouvre la même vue à l'identique.
- **Rétro-compat** : un ancien lien `/dashboard` (sans `?rank=`, partagé avant la feature) affichait la vue agrégée `all`. Après la feature, il affichera la vue `scratch` (le défaut). Ce changement est **assumé** (voir Assumptions de la spec). Un utilisateur qui veut retrouver l'ancienne valeur exacte doit utiliser `?rank=all`.

## Test contract

Un test d'intégration doit couvrir a minima :

1. `/dashboard` (sans paramètre) rend le mode `scratch` (assertion sur le libellé secondaire).
2. `/dashboard?rank=category` rend le mode `category` (libellé « catégorie »).
3. `/dashboard?rank=gender` rend le dédoublement F/H sur les 3 cartes.
4. `/dashboard?rank=all` rend l'agrégation min-des-trois avec libellé « scratch, genre ou catégorie ».
5. `/dashboard?rank=foo` rend `scratch` sans erreur.
6. `/dashboard?rank=category&sports=all` compose les deux filtres (assertion : les stats reflètent les deux).
7. `/club?rank=scratch` filtre la liste des podiums récents pour ne montrer que les podiums scratch.

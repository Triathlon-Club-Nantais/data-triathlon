# Comparaison des segments à la médiane (#1362)

**Objectif** : comparer chaque segment de la page de détail d'une participation à la médiane de tous les classés, et à celle de sa catégorie, sans modifier aucun champ existant de `/api/v1`.

## Décisions (brainstorming tranché seul, options recommandées)

- **Bloc additif `medians`** dans `ParticipationStatsOut`, de type `MedianRow` (`kind`, `label`, `sample_size`, `percentages`, `mine_seconds`, `theirs_seconds`). Pas de ligne dans `comparison` : `ComparisonRow.rank` est un entier requis du contrat publié, une médiane n'a pas de rang, et le rendre nullable modifierait un champ existant (Principe IV).
- **Population** : le classement déjà servi par `list_ranking_for_course` (en attente exclues), lignes avec `rank_overall`, hors relais. La médiane catégorie restreint à la même `category` que l'athlète (catégorie vide : pas de ligne).
- **Garde d'effectif par clé** : `split_gap.MIN_EVALUATED_ROWS` (10) valeurs requises par segment et pour le total, sinon la clé est omise ; une médiane sans aucune clé n'est pas rendue.
- **Médiane arrondie à la seconde** (`theirs_seconds` est entier).
- **T1/T2 indicatifs** : la note existante sur les segments courts les dit « indicatifs ».
- **Rendu** : les médianes s'ajoutent en fin de `ComparisonTable`, avec leur effectif (« 58 classés ») sous le libellé.
- **Aucune requête ajoutée** : calcul en mémoire sur le classement déjà chargé, verrouillé par un test de compte de requêtes.

## Tâches

1. **Service (rouge puis vert)** : effectif suffisant, insuffisant, clé sous le seuil, catégorie, sans catégorie, relais et non classés exclus, ligne en attente et course inéligible sans calcul (`build` rend `None`, tests existants), compte de requêtes constant.
2. **API** : `comparison` garde exactement ses champs, l'enveloppe gagne `medians`.
3. **Front (rouge puis vert)** : `ComparisonTable` rend les médianes et leur effectif, tolère leur absence, dit T1/T2 indicatifs.
4. **Doc** : `backend/app/api/AGENTS.md`.
5. **Vérification** : pytest, ruff, vitest, lint, build.

# Comparaison des segments à la médiane (#1362)

**Objectif** : ajouter à la comparaison de la page de détail d'une participation une ligne « Médiane » (tous classés) et une ligne « Médiane catégorie », sans modifier aucun champ existant de `/api/v1`.

## Décisions (brainstorming tranché seul, options recommandées)

- **Lignes dans `comparison`**, pas un nouveau bloc : le front existant les rend sans changement de forme. Deux champs additifs sur `ComparisonRow` : `kind` (`position` par défaut, `median`, `category_median`) et `sample_size` (effectif sur lequel porte la médiane, `null` pour une position).
- **`rank` vaut 0** sur une ligne de médiane : le champ reste un entier requis (Principe IV), et 0 ne désigne aucune position réelle.
- **Population** : lignes du classement déjà servi par `list_ranking_for_course` (en attente exclues), avec `rank_overall` renseigné, hors relais. La médiane catégorie restreint à la même `category` que l'athlète (vide = pas de ligne).
- **Garde d'effectif par clé** : `split_gap.MIN_EVALUATED_ROWS` (10) valeurs non nulles requises pour chaque segment et le total, sinon la clé est omise ; une ligne sans aucune clé est omise. Pas de zéro inventé.
- **Médiane arrondie à la seconde** (`theirs_seconds` est entier).
- **T1/T2 indicatifs** : la note existante sur les segments courts les dit « indicatifs » ; rien côté API.
- **Aucune requête ajoutée** : tout se calcule sur le classement déjà chargé ; un test de compte de requêtes le verrouille.

## Tâches

1. **Service (rouge puis vert)** : `tests/test_services/test_participation_stats_service.py`, médiane globale et catégorie avec effectif suffisant, insuffisant (ligne absente), clé omise sous le seuil, relais et non classés exclus, ligne en attente et course inéligible sans calcul (`build` rend `None`), nombre de requêtes constant. Puis `_median_rows` dans `participation_stats_service.py`, champs dans `schemas/participation_stats.py`.
2. **API** : le test d'additivité de `ComparisonRow` liste les nouveaux champs, les anciens restent.
3. **Front (rouge puis vert)** : `ComparisonTable.test.tsx`, la ligne « Médiane » s'affiche avec son effectif, la clé React ne repose plus sur `rank`, la note dit T1/T2 indicatifs. Type `ComparisonRow` étendu dans `lib/types.ts`.
4. **Doc** : `backend/app/api/AGENTS.md`, une ligne sur le contrat.
5. **Vérification** : pytest, ruff, vitest, lint, build.

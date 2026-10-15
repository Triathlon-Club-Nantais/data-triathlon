# Fiabilité par fournisseur (#1366)

**Objectif** : sur l'accueil admin, un tableau fournisseur × anomalie (épreuves, épreuves non fiables, décompte par type d'anomalie), pour trancher #1342.

## Décisions (brainstorming tranché seul, options recommandées)

- **Fournisseur** = celui de la source **active** (`CourseSource.is_active`), comme `Course.provider`. Une saisie manuelle (aucune source) n'entre dans aucune ligne.
- **Non fiable** = verdict effectif `Course.is_reliable` faux (avis humain d'abord), la même règle que la file `unreliable=true`. Jamais évaluée (`NULL`) compte dans le total, pas dans les non fiables.
- **Décompte par anomalie** = nombre d'épreuves **non fiables** qui portent ce code, pas la somme des occurrences : la question de #1342 est « combien d'épreuves perd-on », et une épreuve déclarée fiable par un humain ne doit pas gonfler une colonne.
- **Deux requêtes, nombre constant** : un `GROUP BY` fournisseur pour les deux comptes, puis les `quality_issues` des seules épreuves non fiables, agrégées en Python (PostgreSQL et SQLite n'ont pas d'agrégat JSON commun). Verrouillé par un test de compte de requêtes.
- **Route** : `GET /api/v1/admin/quality/providers`, sous `quality:override`, la garde de la revalidation qualité. Additive, aucun champ existant ne change.
- **Rendu** : une section « Fiabilité par fournisseur » sur `/admin`, visible au seul porteur de `quality:override`, colonnes d'anomalie limitées à celles qui apparaissent, libellés de `QUALITY_ISSUE_LABELS`.

## Tâches

1. **Repository (rouge puis vert)** : `course_repository.quality_by_provider` : comptes, source inactive ignorée, avis humain respecté, anomalies des seules non fiables, nombre de requêtes constant.
2. **API (rouge puis vert)** : 200 sous `quality:override`, 403 sans, 401 anonyme.
3. **Front (rouge puis vert)** : `ProviderQualityTable` dans `AdminIndex`, absent sans le pouvoir.
4. **Doc** : `backend/app/api/AGENTS.md`.
5. **Vérification** : pytest, ruff, vitest, lint, build.

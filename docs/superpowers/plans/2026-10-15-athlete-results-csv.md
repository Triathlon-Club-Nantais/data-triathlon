# Export CSV des résultats d'un athlète (#1375)

**Objectif** : `GET /api/v1/athletes/{id}/participations.csv` et un lien de téléchargement sur la fiche athlète.

**Décisions (brainstorming tranché seul)** :

- Mêmes lignes que la fiche : `participation_repository.list_for_athlete` sans filtre, donc carrière entière. Les oppositions (#334) sont appliquées à l'import, la lecture n'a rien à refiltrer. Pas de `seasons`/`federal_only` : aucun appelant.
- Résultats en attente ou refusés : présents, comme sur la fiche, avec une colonne « Validation » (Validé, En attente, Refusé) ; leurs rangs sont vides, comme l'écran qui ne les affiche pas.
- Même garde que `GET /athletes/{id}` : le mot de passe du site, aucun pouvoir RBAC.
- Format Excel français : UTF-8 avec BOM, séparateur `;`, décimale à la virgule. Aucun export CSV n'existait (`sheet_source` ne fait que lire).
- Une colonne « Segment <libellé> » par clé de split (Natation, Vélo, Course… traduits, clés libres telles quelles), union dans l'ordre de première apparition. Le préfixe évite toute collision avec une colonne fixe.
- Cellule texte commençant par `=`, `+`, `@`, tabulation, retour chariot, ou `-` non numérique : préfixée d'une apostrophe (injection de formule, `POST /participations` étant ouvert sans session).
- Statut et discipline restent les jetons stockés (`finisher`, `triathlon-m`) : pas de table de libellés côté backend, à ajouter si le besoin remonte.
- Corps construit en mémoire (`csv` + `io.StringIO`) puis rendu d'un bloc : une carrière tient en quelques centaines de lignes, et la requête passe avant le statut, donc un 404 reste un 404.
- Tri par date d'épreuve décroissante, épreuves sans date en fin.
- Nom de fichier ASCII : `resultats-<prenom>-<nom>.csv`, déaccentué.
- Front : simple lien `<a download>` vers `/api/v1/...` (même origine via le rewrite, le cookie du site part avec la requête).

## Tâches

1. **Tests API (rouge)** dans `tests/test_api/test_athlete_csv_api.py` : en-têtes (`text/csv; charset=utf-8`, `Content-Disposition`), BOM et `;`, contenu d'une ligne validée avec splits, ligne en attente sans rang, 404 sur un athlète inconnu, 401 sans le mot de passe du site.
2. **Implémentation** : `services/athlete_csv.py` (mise en forme), route dans `api/v1/athletes.py`.
3. **Test vitest (rouge)** puis lien « Télécharger toute la carrière (CSV) » dans l'en-tête du tableau `EventsTable`, après la consigne.
4. **Doc** : paragraphe dans `backend/app/api/AGENTS.md`.
5. Vérifications : pytest, ruff, `npm test`, `npm run lint`, `npm run build`.

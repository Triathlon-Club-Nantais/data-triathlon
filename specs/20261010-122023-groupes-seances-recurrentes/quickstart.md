# Quickstart : valider la feature

## Prérequis

- `backend/` : `uv sync`, `uv run alembic upgrade head`, `uv run python scripts/dev_server.py`.
- `frontend/` : `npm ci`, `npm run dev`.
- Un compte portant `jeunes:read` et `jeunes:write`, trois profils ou plus (dont un sans date de naissance, un avec une fin d'adhésion passée).

## Tests automatisés

```bash
cd backend && uv run pytest -m "not integration" -k "training or profile or category"
cd frontend && npx vitest run components/admin/jeunes
```

## Parcours manuels (téléphone, 375 px)

1. **Groupes (US1)** : « Jeunes › Groupes », créer « Benjamins mercredi », ajouter deux profils ; la fiche de chaque profil liste le groupe. Renommer vers un nom existant : refus lisible.
2. **Inscription d'office (US2)** : au calendrier, créer une séance à venir visant ce groupe ; l'appel liste les deux jeunes sans ajout. Ajouter un troisième membre au groupe : il apparaît dans la séance. Pointer un jeune présent, puis retirer un membre du groupe : la séance pointée ne change plus.
3. **Récurrence (US3)** : « Nouvelle récurrence », mercredi 14 h, du 1er octobre au 30 novembre, groupe « Benjamins mercredi » ; l'écran annonce le nombre de séances avant validation ; le calendrier les montre. Changer le lieu d'une séance seule, puis l'heure de la récurrence : la séance modifiée seule garde son heure. Supprimer la récurrence : les séances passées ou pointées restent.
4. **Catégorie (US4)** : la liste affiche la catégorie de chaque profil (« Catégorie inconnue » sans date de naissance) ; filtrer sur une catégorie.
5. **Adhésion terminée** : un profil à fin d'adhésion passée, membre du groupe, n'est pas inscrit aux nouvelles séances.

Résultat attendu : aucun défilement horizontal, aucune présence déjà saisie modifiée.

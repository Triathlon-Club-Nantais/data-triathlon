# Quickstart: Droit d'opposition effectif

## Tests

```bash
cd backend && uv run pytest -m "not integration" && uv run ruff check .
cd frontend && npm test && npm run lint && npm run build
```

## Vérification manuelle (base de dev, `scripts/reset_db.py` avec seed démo)

1. Se connecter en administrateur, ouvrir la fiche d'un athlète classé dans une épreuve.
2. « Appliquer une opposition » : la confirmation annonce le nombre de résultats (homonymes compris) ; confirmer avec une date de demande.
3. Le classement de l'épreuve montre « Anonyme » à son rang, les autres rangs inchangés ; la recherche par son nom ne rend rien.
4. Relancer l'import de l'épreuve (`uv run python -m app.cli rescrape-db --url <url>`) : la ligne reste anonyme, aucune fiche recréée.
5. `/admin/oppositions` : l'opposition est listée avec ses deux dates et son délai, sans nom.
6. Formulaire de signalement : le type « Retrait de mes données » existe ; la demande apparaît typée dans `/admin/retours-utilisateurs`.

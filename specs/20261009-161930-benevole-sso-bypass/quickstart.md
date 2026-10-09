# Quickstart: valider #1272

## Tests automatisés

```bash
# depuis backend/
uv run pytest tests/test_auth/test_benevole_access_sso.py tests/test_api/test_benevoles_api.py
uv run pytest -m "not integration"
uv run ruff check .

# depuis frontend/
npm test
npm run lint
npm run build
```

Attendus : voir les scénarios de `spec.md` (US1 à US3) et la table de `contracts/api.md`.

## Vérification manuelle (dev)

1. Se connecter en SSO avec un compte qui détient `benevole_access:manage`, ouvrir `/benevoles` dans une session sans cookie bénévoles : la file s'affiche, pas de formulaire, pas de bouton « Se déconnecter ».
2. Valider un résultat, puis lire le journal d'administration : l'auteur est ce compte.
3. Se connecter avec un compte sans ce pouvoir : `/benevoles` affiche le formulaire de mot de passe.

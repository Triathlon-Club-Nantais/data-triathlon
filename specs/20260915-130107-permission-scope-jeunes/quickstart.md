# Quickstart: Pouvoir « jeunes »

Validation de bout en bout **sans** route jeunes (elles n'existent pas
encore) : ce que cette issue livre se vérifie par le catalogue et l'écran
d'administration des rôles déjà en place.

## Prérequis

```bash
cd backend
uv sync
uv run alembic upgrade head   # aucune migration nouvelle, juste s'assurer que le schéma est à jour
```

## 1. Le catalogue expose les deux nouveaux pouvoirs

```bash
uv run python -c "
from app.core import permissions
codes = {p.code for p in permissions.ALL}
assert {'jeunes:read', 'jeunes:write'} <= codes, codes
print('OK — jeunes:read et jeunes:write sont dans le catalogue')
"
```

## 2. L'écran d'administration les propose sans modification

```bash
uv run python scripts/dev_server.py &
# Ouvrir la session admin habituelle (SSO GitHub), puis :
curl -s http://localhost:<port>/api/v1/admin/permissions \
  -H "Cookie: <cookie de session avec roles:read>" | python -m json.tool
```

Attendu : un groupe `"feature": "Jeunes"` avec deux pouvoirs, `jeunes:read`
et `jeunes:write`, libellés et descriptions en français.

## 3. Un rôle peut porter le pouvoir

Depuis `/admin/roles` (interface existante), éditer un rôle de test, cocher
« Consulter les jeunes » ou « Encadrer les jeunes », enregistrer. Recharger
l'écran : la case reste cochée. Aucune route jeunes n'existe pour vérifier
l'effet du pouvoir à ce stade — c'est le périmètre des sous-issues #867/#868/#869.

## 4. La suite de tests est verte

```bash
uv run pytest -m "not integration"
uv run ruff check .
```

Attendu : 100 % vert, y compris
`tests/test_permissions_catalogue.py::test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource`
pour `jeunes:read`/`jeunes:write` — via l'exemption documentée décrite dans
`research.md` §Décision 2, pas par une route ajoutée hors périmètre.

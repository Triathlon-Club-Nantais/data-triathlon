# Quickstart — Auth backend GitHub OAuth (#114)

Comment ouvrir une session locale une fois la feature #114 mergée. À copier
dans `AGENTS.md` (section « Authentification » à créer) au moment du merge.

## 1. Créer une application OAuth GitHub personnelle

Un dev qui veut tester l'auth en local crée **son** app OAuth (pas celle du
club) :

1. `https://github.com/settings/developers` → « OAuth Apps » → « New OAuth App »
2. Champs :
   - **Application name** : `tcn-dev-<username>`
   - **Homepage URL** : `http://localhost:3000`
   - **Authorization callback URL** : `http://localhost:8001/api/v1/auth/github/callback`
     (adapter au port du backend, cf. `.dev-backend.json`)
3. « Register application » → noter le **Client ID**
4. « Generate a new client secret » → copier le **Client Secret** (visible une seule fois)

## 2. Configurer `backend/.env`

```env
GITHUB_OAUTH_CLIENT_ID=Iv1.xxxxxxxxxxxxxxxx
GITHUB_OAUTH_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SESSION_SECRET_KEY=<n'importe quelle chaîne longue, ex: python -c "import secrets; print(secrets.token_urlsafe(64))">
SESSION_COOKIE_SECURE=false   # sinon le navigateur ignore le cookie sur http://localhost
FRONTEND_POST_LOGIN_URL=http://localhost:3000/
```

## 3. Appliquer la migration

```bash
cd backend
uv run alembic upgrade head
```

## 4. Lancer le backend et parcourir le flux

```bash
uv run python scripts/dev_server.py
```

Puis dans un navigateur : `http://localhost:8001/api/v1/auth/github/authorize`.

- Le backend redirige vers GitHub.
- On autorise l'app.
- GitHub redirige vers `.../callback?code=…&state=…`.
- Le backend pose `tcn_session` et redirige vers `FRONTEND_POST_LOGIN_URL`.

Pour vérifier la session :

```bash
curl -b <(echo "tcn_session=<valeur du cookie>") http://localhost:8001/api/v1/auth/me
```

Réponse attendue :
```json
{
  "id": 1,
  "email": "toi@example.com",
  "github_login": "ton-login",
  "created_at": "2026-07-31T14:23:00Z"
}
```

## 5. Vérifier la non-régression publique

Sans cookie :
```bash
curl http://localhost:8001/api/v1/courses  # 200, comme avant
curl http://localhost:8001/api/v1/auth/me  # 401
```

## 6. Se déconnecter

```bash
curl -X POST -b "tcn_session=<valeur>" -c cookies.txt http://localhost:8001/api/v1/auth/logout
# 204, et cookies.txt indique tcn_session à Max-Age=0
```

## Notes

- **Aucun rôle admin** — un utilisateur qui a complété le flux n'a accès à
  rien de plus qu'un anonyme. C'est délibéré : #114 livre le socle. #115
  ajoutera les rôles.
- **Rotation de `SESSION_SECRET_KEY`** — toutes les sessions en cours sont
  invalidées, à faire uniquement sur incident (fuite constatée).
- **Aucun stockage du token GitHub** — le backend l'utilise pour lire l'identité
  puis l'oublie. Pas d'action possible côté GitHub au nom de l'utilisateur.

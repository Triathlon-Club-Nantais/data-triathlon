# Contrat API — `/api/v1/auth/*` (#114)

Contrat public exposé au frontend Next.js (#116) et à tout autre client. Une
fois #114 mergé, ce contrat est **stable** au sens Principe IV : un changement
d'incompatible (champ retiré, code de retour modifié, comportement inversé)
motive une v2, pas une modification silencieuse.

## Vue d'ensemble

| Méthode | Chemin | Auth requise | Effet |
|---|---|---|---|
| `GET` | `/api/v1/auth/github/authorize` | Non | Redirige vers GitHub ; pose le cookie `tcn_oauth_state`. |
| `GET` | `/api/v1/auth/github/callback` | Non | Complète le flux OAuth ; pose le cookie `tcn_session` ; redirige vers le front. |
| `POST` | `/api/v1/auth/logout` | Non | Invalide le cookie `tcn_session`. |
| `GET` | `/api/v1/auth/me` | Oui | Renvoie l'utilisateur courant. |

## Cookies

### `tcn_session`

| Attribut | Valeur |
|---|---|
| `Name` | `tcn_session` |
| `HttpOnly` | `true` |
| `SameSite` | `Lax` |
| `Secure` | `true` en production (`SESSION_COOKIE_SECURE=true`), `false` en dev sur `http://localhost` |
| `Path` | `/` |
| `Max-Age` | `604800` (7 jours par défaut, configurable par `SESSION_MAX_AGE_SECONDS`) |
| `Domain` | non défini (host-only cookie) |
| **Payload signé** | JSON `{"uid": <int>, "v": 1}` — signé et horodaté par `itsdangerous.URLSafeTimedSerializer` avec `SESSION_SECRET_KEY` |

### `tcn_oauth_state` (éphémère)

| Attribut | Valeur |
|---|---|
| `Name` | `tcn_oauth_state` |
| `HttpOnly` | `true` |
| `SameSite` | `Lax` |
| `Secure` | idem `tcn_session` |
| `Path` | `/api/v1/auth/github/` |
| `Max-Age` | `600` (10 minutes) |
| **Payload signé** | chaîne `state` (opaque) — signée par la même clé, préfixée pour éviter la confusion avec `tcn_session` |

## Endpoints

### `GET /api/v1/auth/github/authorize`

**Paramètres** : aucun.

**Réponses** :

| Code | Corps | Effets de bord |
|---|---|---|
| `302 Found` | header `Location: https://github.com/login/oauth/authorize?client_id=…&scope=user:email&state=…&redirect_uri=…` | Set-Cookie `tcn_oauth_state=…` |
| `503 Service Unavailable` | `{"detail": "Authentification non configurée."}` | Aucun. Renvoyé si `GITHUB_OAUTH_CLIENT_ID` ou `SESSION_SECRET_KEY` est vide. |

### `GET /api/v1/auth/github/callback`

**Paramètres query** :

| Nom | Type | Obligatoire | Description |
|---|---|---|---|
| `code` | string | oui | Code d'autorisation retourné par GitHub. |
| `state` | string | oui | Doit correspondre exactement au `state` porté par le cookie `tcn_oauth_state`. |
| `error` | string | non | Renseigné si l'utilisateur a refusé (`access_denied`). |
| `error_description` | string | non | Texte GitHub. |

**Réponses** :

| Code | Corps | Effets de bord |
|---|---|---|
| `302 Found` | header `Location: <frontend_post_login_url>` | Set-Cookie `tcn_session=…` ; Delete-Cookie `tcn_oauth_state`. |
| `400 Bad Request` | `{"detail": "État CSRF invalide."}` | Delete-Cookie `tcn_oauth_state`. `state` absent, inconnu, expiré, ou incohérent avec le cookie. |
| `400 Bad Request` | `{"detail": "Autorisation GitHub refusée."}` | Renvoyé si `error=access_denied` ou si `code` refusé. |
| `422 Unprocessable Entity` | `{"detail": "Aucun email GitHub vérifié disponible."}` | L'utilisateur n'a aucun email `verified=true`. |
| `503 Service Unavailable` | `{"detail": "Authentification non configurée."}` | Secrets manquants. |

### `POST /api/v1/auth/logout`

**Paramètres** : aucun.

**Réponses** :

| Code | Corps | Effets de bord |
|---|---|---|
| `204 No Content` | (vide) | Delete-Cookie `tcn_session` (`Max-Age=0`). Idempotent : renvoyé même sans cookie. |

### `GET /api/v1/auth/me`

**Paramètres** : aucun.

**Réponses** :

| Code | Corps | Effets de bord |
|---|---|---|
| `200 OK` | `UserRead` (voir schéma ci-dessous) | Aucun. |
| `401 Unauthorized` | `{"detail": "Non authentifié."}` | Aucun. Cookie absent, invalide, expiré, ou pointant vers un utilisateur inexistant/inactif. |

## Schémas

### `UserRead`

```json
{
  "id": 1,
  "email": "octocat@example.com",
  "github_login": "octocat",
  "created_at": "2026-07-31T14:23:00Z"
}
```

## Non-régression du site public

Les endpoints suivants **doivent** répondre exactement comme avant l'introduction
de l'auth quand aucun cookie de session n'est présent :

- `GET /api/v1/health`
- `GET /api/v1/courses/*`
- `GET /api/v1/athletes/*`
- `GET /api/v1/participations/*`
- `GET /api/v1/scrape/detect`
- `POST /api/v1/scrape/import`
- `GET /api/v1/stats/*`
- `GET /api/v1/admin/*` (le router existe déjà mais n'est **pas** couvert par
  cette sous-issue — sa protection viendra en #115. À #114, il reste ouvert
  comme aujourd'hui.)

## Contrats internes (dépendances FastAPI)

Exposés dans `app/api/deps.py`, à réutiliser par les sous-issues #115+ :

- `current_user(db: Session = Depends(get_db), request: Request) -> User` —
  lève `HTTPException(401)` si absent/invalide.
- `current_user_optional(db: Session = Depends(get_db), request: Request) -> User | None` —
  jamais d'exception ; renvoie `None` si absent/invalide.

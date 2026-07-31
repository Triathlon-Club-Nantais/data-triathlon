# Research — Auth backend GitHub OAuth (#114)

Phase 0. Résolution des inconnues techniques du plan.

Chaque décision suit le format « Decision / Rationale / Alternatives considered »
demandé par `/speckit-plan`.

## 1. Bibliothèque de signature du cookie de session

**Decision** — `itsdangerous.URLSafeTimedSerializer`.

**Rationale** — installée transitivement par FastAPI/Starlette (déjà dans
`uv.lock` via `starlette` — pas de nouvelle dépendance à déclarer, ni à faire
valider en review). Le sérialiseur signé + horodaté couvre exactement ce qu'on a
besoin de garantir : vérification HMAC de la signature *et* détection
d'expiration côté serveur (via `max_age` à la désérialisation). Le payload est
un simple `dict` — pas de complexité JWT (algorithmes, `kid`, JWK) qu'on n'aurait
aucune raison d'invoquer sur un cookie unique porté par notre seul backend. La
rotation de `SECRET_KEY` invalide immédiatement toutes les sessions en cours,
comportement voulu et documenté dans la spec (edge case).

**Alternatives considered** :
- **PyJWT** (JWT stateless en Bearer) — écarté par la spec elle-même (choix
  utilisateur : cookie HttpOnly signé, pas de token en Authorization header).
  Même si on l'utilisait pour signer un cookie, on paierait la surface d'attaque
  historique de JWT (`alg: none`, confusion HS/RS) pour zéro bénéfice ici.
- **`Fernet` (`cryptography`)** — chiffre + signe, mais ajoute `cryptography` à
  la surface de dépendances et cache le payload. On n'a rien à cacher (un
  `user_id` int) : la signature suffit. La lisibilité du payload en dev est un
  atout, pas un défaut.
- **`starlette.middleware.sessions.SessionMiddleware`** — Starlette expose déjà
  un middleware de session basé sur `itsdangerous`. Il stocke un `dict`
  entier signé dans le cookie. Écarté parce qu'il pose son propre cookie sans
  laisser choisir le nom, le `SameSite`, ni surtout le `max_age` de façon
  fine (le middleware l'aligne sur `session_cookie` mais expose peu de leviers).
  Envelopper directement `URLSafeTimedSerializer` coûte 10 lignes et nous rend
  la maîtrise complète.

## 2. Modèle utilisateur — schéma exact et relation à `Athlete`

**Decision** — table `users` séparée, avec une FK **nullable** vers `athletes`.

Colonnes :
| Nom | Type | Contraintes | Rôle |
|---|---|---|---|
| `id` | `Integer` | PK | Identifiant applicatif |
| `github_id` | `String` | `UNIQUE`, `NOT NULL`, `index=True` | Clé de dédoublonnage (voir Rationale) |
| `github_login` | `String` | `NOT NULL` | Login GitHub (peut évoluer côté GitHub) |
| `email` | `String` | `NOT NULL`, `index=True` | Email vérifié GitHub |
| `is_active` | `Boolean` | `NOT NULL`, `default=True` | Désactivation sans suppression |
| `created_at` | `DateTime` | `NOT NULL`, `default=utcnow` | Horodatage de première connexion |
| `athlete_id` | `Integer` | `FK(athletes.id) ON DELETE SET NULL`, `nullable=True` | Rapprochement optionnel (exploité par les sous-issues suivantes) |

**Rationale** —

- `github_id` **`String`** (et non `Integer`) : GitHub renvoie un int 64 bits sur
  les nouveaux comptes ; SQLite fait de l'int 64 sans effort, mais un `Integer`
  Alembic tape en `INTEGER` sur SQLite et en `INTEGER` (32 bits) sur Postgres.
  Le stocker en `String` élimine ce piège pour cinq caractères de plus, et laisse
  la porte ouverte à d'autres providers plus tard sans migration (pas dans le
  périmètre, mais gratuit).
- `github_id UNIQUE` : c'est la clé de rapprochement de FR-007. `email UNIQUE`
  serait une erreur — un humain peut changer d'email GitHub tout en gardant son
  `github_id` (raison de FR-010, edge case du spec).
- `athlete_id` **`ON DELETE SET NULL`** : supprimer un athlète ne doit pas
  ricocher en cascade sur un utilisateur applicatif. La direction inverse
  (suppression d'un user → athlete conservé) est de toute façon triviale car la
  FK est portée côté `users`.
- `is_active` mais **pas** `is_admin` ni `role` : la spec renvoie explicitement
  RBAC à #115. Ajouter un champ inutile aujourd'hui contredit le Principe VI
  (YAGNI). Ce sera une migration Alembic dédiée dans #115.
- Pas de `password_hash` : décision structurante de la spec (GitHub OAuth seul,
  pas de fallback local).

**Alternatives considered** :
- **Fusion avec `Athlete`** — écartée à la spécification. Le rappel du
  raisonnement : `Athlete` est peuplé par les scrapers (des milliers de fiches
  sans notion applicative), l'unicité de `Athlete` est `(nom, prenom,
  birth_date)`, incompatible avec l'unicité par email/`github_id`.
- **`github_id INTEGER`** — plus léger mais expose au débordement 32 bits en
  Postgres. Coût nul de passer en `String`.
- **Ajouter `sessions` tout de suite** — écarté par la spec (« session dans un
  cookie signé, révocation immédiate = besoin non identifié »). Ré-évaluable si
  le besoin de révocation surgit.

## 3. Format et durée du cookie de session

**Decision** — cookie unique `tcn_session`, portant un dict JSON signé et
horodaté par `URLSafeTimedSerializer`.

- **Payload** : `{"uid": <int>, "v": 1}`. Un seul champ métier (`uid`, l'ID
  applicatif). Version `v` pour ménager une évolution future du format sans
  invalider tout le monde (on peut ignorer les payloads dont `v` n'est plus
  supportée).
- **Attributs cookie** : `HttpOnly=True`, `SameSite="Lax"`,
  `Secure=<settings.session_cookie_secure>`, `Path="/"`,
  `Max-Age=<settings.session_max_age_seconds>`.
- **Durée** : 7 jours par défaut (`session_max_age_seconds=604800`). C'est le
  compromis retenu ailleurs pour du cookie d'authentification web (assez court
  pour limiter le vol, assez long pour que l'utilisateur ne se reconnecte pas
  chaque matin).
- **Signature d'expiration** : `URLSafeTimedSerializer.loads(token,
  max_age=session_max_age_seconds)` — la même valeur qu'on donne au cookie côté
  navigateur. Deux gardes contre l'expiration : le navigateur qui refuse
  d'envoyer un cookie expiré, et le backend qui refuse un payload trop vieux.

**Alternatives considered** :
- **Durée « session navigateur »** (sans `Max-Age`) — écartée, incompatible avec
  la vérification `max_age` côté serveur et rend l'expérience aléatoire selon
  les navigateurs.
- **Rolling window** (le cookie se prolonge à chaque requête) — écarté par
  Principe VI (YAGNI, aucun besoin exprimé) et parce que ça complique la
  révocation (à quel moment coupe-t-on ?).

## 4. Contrat OAuth GitHub — endpoints et paramètres

**Decision** — flux OAuth2 authorization code standard, `scope=user:email`.

- **`/api/v1/auth/github/authorize`** :
  - Génère un `state` aléatoire (`secrets.token_urlsafe(32)`).
  - Pose un cookie court `tcn_oauth_state` (`HttpOnly`, `SameSite=Lax`,
    `Max-Age=600`) qui contient uniquement ce `state` (signé par la même clé,
    version indépendante du cookie de session).
  - Renvoie `RedirectResponse(302)` vers
    `https://github.com/login/oauth/authorize?client_id=…&scope=user:email&state=…&redirect_uri=…`.
- **`/api/v1/auth/github/callback`** :
  - Lit `code` et `state` en query.
  - Vérifie `state` contre le cookie `tcn_oauth_state` (signature + égalité
    stricte). Le cookie est supprimé quelle que soit l'issue.
  - Échange `code` contre un access token via
    `POST https://github.com/login/oauth/access_token` (header `Accept:
    application/json` pour un payload JSON plutôt qu'urlencoded).
  - `GET https://api.github.com/user` pour `id`, `login`, `email`.
  - Si `email` est absent : `GET https://api.github.com/user/emails`, on
    retient le premier email `verified=true` et `primary=true`, à défaut le
    premier `verified=true`.
  - Le token GitHub est utilisé pour ces deux appels puis oublié (pas de
    stockage, cf. FR-008).
  - Pose le cookie `tcn_session`, redirige vers
    `settings.frontend_post_login_url` (destination configurée statiquement, pas
    un paramètre d'entrée — cf. spec, ouvre l'« open redirect » sinon).
- **`/api/v1/auth/logout`** : supprime `tcn_session` (`Max-Age=0`), 204.
- **`/api/v1/auth/me`** : lit `tcn_session`, renvoie l'utilisateur (200) ou 401.

**Rationale** — le scope `user:email` est le minimum pour lire les emails
vérifiés d'un compte (l'`email` public seul manque quand l'utilisateur l'a
masqué — cf. edge case du spec). Le `state` en cookie signé plutôt qu'en session
serveur évite de créer une table `oauth_states` pour un jeton qui vit 10
minutes. Le rejet strict (état absent → refus) et non « best-effort » (« si pas
de state, ok ») est la ligne rouge CSRF.

**Alternatives considered** :
- **`authlib`** — bibliothèque OAuth mature. Ajoute une dépendance et pas mal
  d'abstractions pour un flux qui tient en 40 lignes de `httpx`. Écarté par
  Principe VI.
- **Ne pas demander `user:email`** — irréaliste : sans le scope, la clé de
  contact d'un utilisateur reste `null`.
- **Rediriger vers `settings.frontend_url + "/admin"` en dur** — écarté au
  profit d'une variable dédiée (`frontend_post_login_url`), car le back-office
  n'existe pas encore (#116 le livrera). En attendant, on redirige vers l'accueil
  ou vers une page de courtoisie.

## 5. Dépendances FastAPI de reconnaissance de l'utilisateur

**Decision** — deux dépendances dans `app/api/deps.py` :

- **`current_user(db, request) -> User`** — obligatoire, lève 401 si session
  absente/invalide. À utiliser par les routes qui *exigent* un utilisateur
  connecté (typiquement `GET /api/v1/auth/me`).
- **`current_user_optional(db, request) -> User | None`** — accepte les
  anonymes. À utiliser par les routes publiques qui *peuvent* enrichir la
  réponse quand un utilisateur est connu (aucune sur ce ticket ; la dépendance
  existe pour FR-016).

Les deux passent par `app.services.auth_service.get_user_from_session`, seul
point qui déchiffre le cookie et rappelle le repository. **Zéro** `Session` SQL
en dehors du repository (Principe II).

**Rationale** — la spec (FR-016) demande explicitement les deux comportements.
Deux dépendances sont plus lisibles qu'un paramètre `required=True/False` — le
type de retour (`User` vs `User | None`) rend la contrainte visible dans les
signatures.

**Alternatives considered** —
- **Middleware qui pose `request.state.user`** — écarté, ce pattern rend
  invisible dans la signature d'un endpoint l'existence ou non d'un utilisateur
  attendu, et casse `Depends(current_user)` qui reste plus explicite.

## 6. Gestion des secrets

**Decision** — trois variables dans `Settings`, ajoutées à `backend/.env.example`
avec des valeurs vides et un commentaire indiquant qu'elles doivent être
remplies pour activer l'authentification :

- `github_oauth_client_id: str = ""`
- `github_oauth_client_secret: str = ""`
- `session_secret_key: str = ""`
- `session_max_age_seconds: int = 604800`  # 7 jours
- `session_cookie_secure: bool = True`  # `False` en dev via env var
- `frontend_post_login_url: str = "/"`
- `github_oauth_redirect_url: str | None = None`  # défaut : URL de callback du backend

Si `session_secret_key` est vide **et** qu'on tente d'ouvrir une session,
l'endpoint concerné lève une `DomainError` française (« Authentification non
configurée. »). Cela satisfait FR-020 : l'API publique reste fonctionnelle même
sans secrets, seuls les endpoints d'auth deviennent indisponibles avec un
message clair.

**Alternatives considered** —
- **Générer une clé aléatoire au démarrage si absente** — écarté : rendrait
  toute redémarrage invalidant. En dev, l'opérateur définit une clé bidon dans
  `.env` ; en prod, elle est configurée sur Render.

## 7. Stratégie de test (Principe III non-négociable)

**Decision** — monkeypatch de `httpx.Client` (ou `AsyncClient` si besoin), comme
`test_klikego.py`. Les payloads GitHub (`/user`, `/user/emails`,
`/login/oauth/access_token`) sont figés en fixtures.

Structure :
```
backend/tests/test_auth/
├── __init__.py
├── test_session_cookie.py       # sign/verify/expiry/rotation
├── test_github_oauth_flow.py    # authorize → callback (success + refus)
├── test_deps_current_user.py    # current_user vs current_user_optional
├── test_public_routes_still_open.py  # non-régression accès public
└── fixtures/
    ├── github_user.json
    └── github_user_emails.json
```

- **Pas de réseau** : chaque test qui simule un appel GitHub monkeypatche
  `httpx.Client.post` / `httpx.Client.get` (ou l'équivalent async). Cf.
  `test_klikego.py`.
- **Base isolée en mémoire** : la fixture `db_session` de `conftest.py` couvre
  déjà ce cas — on ajoute un modèle, elle en tient compte automatiquement (elle
  fait `Base.metadata.create_all(bind=engine)`).

**Rationale** — c'est la seule convention du dépôt (`respx` est dans
`dependency-groups.dev` mais n'est plus la convention selon Principe III et le
Sync Impact Report). Cohérence >> nouveau pattern.

## 8. Migration Alembic

**Decision** — une révision unique `feat_user_table` (nom explicite, pas
d'auto-généré) qui :

- crée la table `users` avec les colonnes ci-dessus,
- crée les index sur `github_id` (UNIQUE) et `email` (non-unique),
- crée la FK `athlete_id → athletes.id ON DELETE SET NULL`.

`downgrade()` : `drop_table('users')`. Aucun impact sur les tables existantes,
donc aucune donnée à migrer.

**Rationale** — le workflow standard du dépôt (`uv run alembic revision
--autogenerate` puis relecture) marche pour cette feature. La relecture manuelle
consistera à vérifier que la révision ne modifie **rien** sur les autres tables
(garantie de FR-018).

## 9. AGENTS.md — section « Authentification »

**Decision** — nouvelle section, placée après « Architecture backend », avant
« Fournisseurs supportés ». Environ 30-40 lignes.

Contenu :
- ce qui est protégé et ce qui ne l'est pas ;
- endpoints d'auth (`authorize`, `callback`, `logout`, `me`) ;
- variables d'environnement (`GITHUB_OAUTH_CLIENT_ID`,
  `GITHUB_OAUTH_CLIENT_SECRET`, `SESSION_SECRET_KEY`,
  `SESSION_COOKIE_SECURE`) ;
- comment ouvrir une session en local (créer une app OAuth GitHub, mettre les
  secrets dans `.env`, désactiver `SESSION_COOKIE_SECURE`) ;
- ce qui est renvoyé à #115 (rôles, RBAC, `create-admin`).

## 10. Points laissés ouverts (documentés, hors périmètre de #114)

- **Révocation immédiate de session** — pas de table `sessions`, la rotation de
  `SESSION_SECRET_KEY` fait office de kill-switch global. Ouverture possible en
  #117 (audit trail) ou en cas d'incident.
- **Refresh token** — inutile ici (pas de token GitHub stocké, la session
  applicative dure 7 jours, l'utilisateur reprend le flux OAuth à l'expiration).
- **Support d'un second provider** — le repository et le service sont conçus
  pour être élargis (paramètre `provider`) mais on n'anticipe **pas** dans le
  code : `github_id` reste `github_id`. Si Google Workspace arrive, il faudra
  soit une colonne `provider` + `provider_id`, soit une table `identities`
  séparée. YAGNI.

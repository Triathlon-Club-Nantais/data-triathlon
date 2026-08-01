# Sondage — bibliothèques OAuth/SSO pour le socle d'authentification (#114)

**Date** : 2026-08-01
**Objet** : choisir la brique OAuth du socle d'authentification, en remplacement de la PR #159.
**Statut** : sondage. Il **prime** sur le design, la spec et le plan. Toute divergence se tranche
en re-sondant.

## Méthode

Les trois paquets ont été **installés** dans un environnement jetable (`uv venv`, Python 3.13) et
inspectés dans leur code source, pas dans leur documentation. Les affirmations ci-dessous sont
des mesures reproductibles, pas des lectures de README. Deux affirmations issues d'une recherche
documentaire se sont d'ailleurs révélées **fausses** à la vérification (voir §5) — d'où cette
règle de méthode.

Versions sondées : `fastapi-sso` 0.21.1, `httpx-oauth` 0.17.0, `authlib` 1.7.2.

## 1. La contrainte qui décide : l'injection du client HTTP

`AGENTS.md` impose que **toute sortie HTTP de `app/` passe par `app.core.http.client()`**, qui
enveloppe le transport d'une garde de destination (#101), et un méta-test AST
(`tests/test_core_http.py::test_meta_aucun_httpx_nu_dans_app`) refuse tout `httpx` nu. Une
bibliothèque OAuth n'est donc utilisable ici que si elle laisse **injecter son client httpx**.

| Paquet | Injection possible ? | Mesure |
| --- | --- | --- |
| `fastapi-sso` | **Non** | `httpx.AsyncClient()` instancié en dur dans `sso/base.py:589` (`process_login`, chemin nominal de tout login) et `sso/google.py:33`. Aucun paramètre, attribut ni méthode d'extension. |
| `httpx-oauth` | **Partiellement** | `get_httpx_client()` existe et est utilisé par `oauth2.py` (3 sites). **Mais** `GitHubOAuth2.get_profile` et `get_emails` court-circuitent la fabrique (`clients/github.py:110` et `:144`). GitHub est le **seul** client du paquet dans ce cas ; les onze autres passent bien par la fabrique. |
| `authlib` | **Oui, nativement** | `authlib.integrations.httpx_client.OAuth2Client` **hérite de `httpx.Client`** (MRO vérifié) ; ses `**kwargs` descendent au constructeur httpx, donc `transport=` s'applique. Aucune surcharge, aucune ligne recopiée. |

## 2. Synchrone ou asynchrone

Le backend est **intégralement synchrone** : 24 routes `def`, zéro `async def`, SQLAlchemy 2.0
sync.

- `fastapi-sso` : **async seul**. Le `__enter__` synchrone est un vestige déprécié ; les méthodes
  utiles restent des coroutines.
- `httpx-oauth` : **async seul**.
- `authlib` : **les deux**. `authlib.integrations.httpx_client` exporte `OAuth2Client` (sync) *et*
  `AsyncOAuth2Client`. Attention au piège : `authlib.integrations.requests_client.OAuth2Session`
  est bien synchrone mais bâti sur `requests`, donc **hors de portée de la garde** — ce n'est pas
  celui qu'il faut. Le bon est `httpx_client.OAuth2Client`.

## 3. Sécurité du flux, telle que livrée

Mesuré sur les classes réellement importées :

```
fastapi_sso.sso.github.GithubSSO.requires_state = False
fastapi_sso.sso.github.GithubSSO.uses_pkce      = False
```

Toute la validation de l'état CSRF de `fastapi-sso` est conditionnée à `requires_state`
(`sso/base.py`, lignes 408-415). Conséquence : **le flux GitHub livré par `fastapi-sso` n'a ni
PKCE ni validation d'état**. C'est le scénario de la CVE-2025-14546 ; le correctif est présent
dans le code mais inerte pour 19 providers sur 20. Une sous-classe posant `requires_state = True`
le réarme, mais l'état voyage alors dans un cookie ni signé, ni `HttpOnly`, ni `Secure`, et jamais
supprimé après usage.

Authlib produit `state` et PKCE S256 nativement, à condition de passer
`code_challenge_method="S256"` au constructeur — **sans ce paramètre, `create_authorization_url`
ignore silencieusement le `code_verifier` fourni** et n'émet aucun `code_challenge`. Mesuré : le
piège est réel, l'appel ne lève pas.

## 4. Preuve de bout en bout (Authlib + garde du projet)

Script exécuté avec `app.core.http._GuardTransport` réel et un `httpx.MockTransport` interne :

- URL d'autorisation émise avec `state` **et** `code_challenge` + `code_challenge_method=S256` ;
- `fetch_token()` et l'appel d'identité **tous deux vus par le transport gardé** (2 requêtes sur 2) ;
- une destination interne (`http://169.254.169.254/`) est **refusée** par la garde, depuis Authlib.

Conclusion : la garde anti-SSRF s'applique à l'intégralité du flux OAuth, sans surcharge ni fork,
et `transport=` sert en outre de couture de test (aucun monkeypatch de symbole global, aucun
réseau — Principe III).

## 5. Deux affirmations de la documentation, démenties par la mesure

1. « Le mode synchrone d'Authlib repose sur `requests`, donc hors de portée d'une garde httpx. »
   **Faux** — vrai de `requests_client`, faux de `httpx_client.OAuth2Client`, qui est synchrone
   *et* httpx.
2. « GitHub ne supporte pas PKCE, `code_challenge` y est ignoré. »
   **Faux depuis le 14 juillet 2025** — GitHub a ajouté PKCE aux OAuth Apps et aux GitHub Apps
   ([changelog](https://github.blog/changelog/2025-07-14-pkce-support-for-oauth-and-github-app-authentication/)).
   La documentation actuelle de `GET /login/oauth/authorize` liste `code_challenge` et
   `code_challenge_method` (S256 seul, `plain` non supporté) et celle de
   `POST /login/oauth/access_token` liste `code_verifier`, tous « fortement recommandés ».

## 6. Contraintes d'exécution mesurées, à connaître pour le design

- **Limiteur de threads AnyIO : 40** (`anyio.to_thread.current_default_thread_limiter().total_tokens`).
  Toutes les routes du projet étant `def`, elles s'exécutent dans ce pool : 40 requêtes lentes
  concurrentes saturent l'API entière. Un endpoint qui fait deux allers-retours réseau vers
  GitHub est donc un levier de déni de service sur le site public — d'où l'ordre imposé
  « toute validation locale avant le moindre octet réseau ».
- **httpx réémet le corps sur une redirection 307/308** : `Client._redirect_headers` retire
  `Authorization` en cross-origin, mais `_redirect_stream` rend `request.stream` tel quel dès que
  la méthode est préservée. Le corps de l'échange de jeton portant `client_secret`, l'`OAuth2Client`
  du fournisseur doit poser `follow_redirects=False` — la garde de destination, elle, n'interdit
  pas une redirection vers un autre domaine **public** (l'export CSV du Google Sheet en dépend).

## 7. Angle mort du méta-test anti-SSRF sur `OAuth2Client`

Mesuré en appelant directement le détecteur `_httpx_nu` de `tests/test_core_http.py` :

| Source analysée | Lignes fautives rendues |
| --- | --- |
| `import httpx` + `httpx.Client(timeout=1)` | `[2]` |
| `from authlib.integrations.httpx_client import OAuth2Client` + `OAuth2Client(client_id="x")` | **`[]`** |

Le détecteur ne flague qu'un appel dont la cible est liée **au module `httpx`** (`ast.Import`) ou
importée **de `httpx`** (`ast.ImportFrom` avec `module == "httpx"`). `OAuth2Client` échappe donc
aux deux, alors qu'il **hérite de `httpx.Client`** et ouvre de vraies connexions. Son propre test
de spécification asserte d'ailleurs ce comportement (« un `Client` homonyme venu d'ailleurs n'est
pas celui d'httpx »).

Conséquence : introduire Authlib sans précaution ajouterait à `app/` la **première** sortie HTTP
que le filet de #101 ne voit pas — à l'endroit exact où circulent un `client_secret` et un code
d'autorisation. `httpx.HTTPTransport()` est dans le même cas (absent de `_VERBES_HTTPX`).

Deux gestes s'imposent donc, et ils ne sont pas optionnels :

1. exposer une fabrique publique `guarded_transport()` dans `app/core/http.py` — `client()` rend
   un `httpx.Client` déjà construit, inutilisable pour Authlib, et `_GuardTransport` est privé.
   Sans elle, il n'existe **aucune voie légale** et la docstring de `client()` (« **Seule** voie
   de sortie de `app/` ») devient fausse ;
2. **étendre le détecteur existant** — jamais en écrire un second, la règle « une seule
   définition » (#33, #76) valant aussi pour les gardes — en y ajoutant les liaisons
   d'`authlib.integrations.httpx_client` et les verbes `HTTPTransport` / `AsyncHTTPTransport`.

## 8. Dépendances

- `authlib` 1.7.2, licence BSD-3-Clause, deux dépendances transitives : `cryptography`, `joserfc`.
- `joserfc` couvre le besoin de signature du jeton d'état court (JWS HS256 + validation `exp` +
  rejet sur mauvaise clé, vérifié) : **`itsdangerous` devient inutile**, contrairement au choix
  de la PR #159.
- `itsdangerous` n'est **pas** dans `backend/uv.lock` aujourd'hui : c'était bien une dépendance
  nouvelle de #159, pas un transitif de `fastapi[standard]`.
- Constat annexe : `respx` est déclaré en dépendance de développement dans
  `backend/pyproject.toml` mais **n'est utilisé par aucun test**.

## 9. Décision

**Authlib**, via `authlib.integrations.httpx_client.OAuth2Client` (synchrone), avec le transport
gardé du projet, `follow_redirects=False`, `timeout` explicite et
`code_challenge_method="S256"`.

`fastapi-sso` est écarté sur deux faits rédhibitoires : client httpx non injectable (donc garde
anti-SSRF contournée, ou ~80 lignes d'oauthlib à recopier et rediffer) et flux GitHub livré sans
PKCE ni validation d'état. `httpx-oauth` est écarté de peu : bon point d'extension, mais son
client GitHub le court-circuite sur deux méthodes, et il est async-seul là où Authlib permet de
ne pas toucher au caractère synchrone du backend.

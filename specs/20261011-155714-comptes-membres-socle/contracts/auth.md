# Contrat : authentification (#1322, #1323)

## `GET /api/v1/auth/methods` (inchangé en forme)

Ajoute `{"slug": "entra", "label": "Google ou code par e-mail"}` dès que `AUTH_ENTRA_SUBDOMAIN`, `AUTH_ENTRA_TENANT_ID`, `AUTH_ENTRA_CLIENT_ID` et `AUTH_ENTRA_CLIENT_SECRET` sont posés (et que le socle est configuré). Absent sinon.

## `GET /api/v1/auth/entra/authorize` (route générique existante)

302 vers `https://{subdomain}.ciamlogin.com/{tenantId}/oauth2/v2.0/authorize` avec `response_type=code`, `client_id`, `redirect_uri={AUTH_REDIRECT_BASE_URL}/api/v1/auth/entra/callback`, `scope=openid profile email`, `state`, `nonce`, `code_challenge` (S256). `round_trip` signé dans le cookie d'état : `{"verifier", "nonce"}`. Aucun appel réseau.

## `GET /api/v1/auth/{provider}/callback` (existante)

- Succès : 302 vers `{AUTH_REDIRECT_BASE_URL}/admin` si l'utilisateur administre, **sinon** `{AUTH_REDIRECT_BASE_URL}/` (changement #1322).
- Échec : 302 vers `/login?error=<code>`, ensemble fermé inchangé (`state_mismatch`, `email_unverified`, `account_not_allowed`, `provider_error`, `provider_unavailable`).
  - `account_not_allowed` ne signifie plus « adresse hors liste » mais « compte désactivé » (libellé d'interface à mettre à jour).
  - Entra : jeton invalide (signature RS256, `iss`, `aud`, `nonce`, `exp`, `nbf`, `oid` absent) ou découverte hors du tenant (émetteur ou `jwks_uri` hors de `*.ciamlogin.com` ou sans l'identifiant du tenant) → `provider_error` ; le compte est résolu par `(entra, oid)`, jamais par `sub` ; découverte, JWKS ou jeton injoignables → `provider_unavailable` ; e-mail absent ou `xms_edov` différent de `true` → `email_unverified`.

## `GET /api/v1/auth/me` (ajout)

Champ additif `is_member: boolean` (statut adhérent dérivé à la requête). Les autres champs sont inchangés.

## Garde du code d'accès (`require_site_access`)

Ordre : cookie de site valide → accès ; sinon session d'un compte adhérent → accès (même sans code configuré) ; sinon 401 `site_access_required` (inchangé). `GET /site-access/session` suit la même règle.

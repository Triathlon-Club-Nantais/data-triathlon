# Contrat public — `/api/v1/auth/*`

Phase 1. Cinq endpoints **nouveaux**. Aucun contrat existant n'est modifié (Principe IV).

**Invariant transverse** : toutes les réponses de ce préfixe portent `Cache-Control: no-store` et
`Vary: Cookie`, posés par une dépendance de router — jamais endpoint par endpoint. Une réponse
portant une identité traverse la réindirection de l'interface et ne doit jamais pouvoir être servie
à un autre visiteur (FR-018).

**Cookies** :

| Cookie | Durée | Attributs | Contenu |
| --- | --- | --- | --- |
| `__Host-tcn_session` | 7 jours | `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, **jamais** `Domain` | Jeton opaque, 43 caractères. |
| `__Host-tcn_auth_state` | 10 minutes | idem | JWS `{state, round_trip, provider, exp}`. |

En développement sans TLS, le préfixe `__Host-` est retiré du nom (il exige `Secure`) : les noms
deviennent `tcn_session` et `tcn_auth_state`. Le nom est **dérivé** du réglage, jamais bricolé au
cas par cas.

---

## `GET /api/v1/auth/methods`

Moyens de connexion **effectivement disponibles**. C'est la source de l'écran de connexion : aucune
liste n'est codée en dur côté interface (FR-031).

**200**
```json
[{ "slug": "github", "label": "GitHub" }]
```

Rend `[]` — et non une erreur — quand l'authentification n'est pas configurée ou que la liste des
comptes autorisés est vide (FR-007, FR-036). Une liste vide est une réponse **valide** qui signifie
« aucune connexion possible » ; l'interface l'affiche comme telle.

Jamais authentifié. Ne révèle aucun secret ni aucune adresse.

---

## `GET /api/v1/auth/{provider}/authorize`

Ouvre le parcours. **302** vers le fournisseur, avec `Set-Cookie: __Host-tcn_auth_state=…`.

| Cas | Réponse |
| --- | --- |
| Fournisseur configuré et autorisé | **302** vers le fournisseur |
| `provider` inconnu du registre | **404** |
| Authentification non configurée | **503**, `{"detail": "…"}` en **français** |

Ne prend **aucun** paramètre. En particulier, aucune destination de retour (FR-026) : elle vient de
la configuration, ce qui ferme la redirection ouverte par construction.

Ne crée **aucune** ligne en base : l'état vit dans le cookie signé. Cet endpoint est donc quasi
gratuit et n'offre aucun levier de croissance à un anonyme.

---

## `GET /api/v1/auth/{provider}/callback`

Retour du fournisseur. **Répond toujours par une redirection** — jamais par une page de données
(FR-027).

**Succès** → **302** vers la destination configurée, avec `Set-Cookie: __Host-tcn_session=…` et
effacement du cookie d'état.

**Échec** → **302** vers `/login?error=<code>`, avec effacement du cookie d'état.

Codes d'erreur — **ensemble fermé**, valeurs anglaises, traduites en français par l'interface :

| Code | Cause |
| --- | --- |
| `state_mismatch` | Preuve d'origine absente, altérée, expirée, déjà consommée, ou émise pour un autre moyen de connexion. |
| `email_unverified` | Le fournisseur ne certifie aucune adresse pour cette personne. |
| `account_not_allowed` | Adresse absente de la liste des comptes autorisés. |
| `provider_error` | Le fournisseur a refusé, ou a répondu de façon inexploitable. |
| `provider_unavailable` | Le fournisseur est injoignable. |

Aucune autre valeur n'est jamais émise. En particulier, **aucun message provenant du fournisseur ni
aucune donnée d'entrée** n'atteint ce paramètre : la correction du défaut de la PR #159 — qui
affichait une page JSON brute — ne doit pas ouvrir une injection dans la page de connexion.

**Ordre d'exécution, contractuel** (FR-025) :

1. lecture et vérification du cookie d'état (signature, expiration, correspondance du `state`,
   correspondance du `provider` avec le segment d'URL) ;
2. **effacement du cookie d'état** — c'est l'usage unique, et il précède le réseau ;
3. présence du `code` ;
4. **puis seulement** : échange du code, puis récupération de l'identité (au plus deux allers-retours) ;
5. certification de l'adresse, **puis** liste des comptes autorisés ;
6. résolution de l'identité, ouverture de la session.

Cet ordre n'est pas une préférence de style : le limiteur de threads mesuré à 40 fait d'un retour
de parcours coûteux un levier de déni de service **sur le site public**. Un test vérifie qu'aucun
octet ne part sur les chemins d'échec local.

Un échec **ne laisse jamais d'utilisateur enregistré** (FR-006).

---

## `POST /api/v1/auth/logout`

Ferme **cette** session. **204**, sans corps, avec effacement du cookie de session.

Idempotent : **204** également sans cookie, avec un cookie invalide, ou avec une session déjà
close. Ne rend jamais 401 — se déconnecter d'une session absente est un succès.

Les autres sessions du même utilisateur **survivent** (FR-014). C'est une différence de
comportement assumée avec la PR #159, dont la déconnexion fermait tous les appareils.

`POST` et non `GET` : le cookie étant `SameSite=Lax`, un `POST` d'origine tierce ne le porte pas.

---

## `GET /api/v1/auth/me`

| Cas | Réponse |
| --- | --- |
| Session valide | **200** |
| Absente, invalide, expirée, ou compte désactivé | **401**, `{"detail": "…"}` en **français** |

**200**
```json
{
  "id": 1,
  "email": "contributeur@example.org",
  "display_name": "thomas",
  "created_at": "2026-08-01T14:54:28.000000Z"
}
```

**401 et non « 200 avec un corps nul »** : c'est le point de contrat à verrouiller maintenant, car
en changer plus tard inverserait une sémantique — ce que le Principe IV proscrit. Un test le fige.

`display_name` vient du fournisseur et sert à l'affichage. Ni l'identifiant opaque chez le
fournisseur, ni l'identifiant de session, ni aucun jeton ne sont exposés.

**Ajouts non cassants prévus** : `role` (#115) et `athlete_id` (#117). Ajouter un champ ne rompt
pas le contrat au sens du Principe IV, qui vise le champ retiré, la sémantique inversée et le code
de retour modifié.

---

## Ce que ce contrat n'offre pas, délibérément

- Aucun endpoint de **création de compte** : un compte naît d'une connexion réussie et autorisée.
- Aucun endpoint de **liaison** de deux identités (`/link`) : le mécanisme n'est pas livré, et son
  absence est nommée pour qu'on ne le croie pas acquis.
- Aucun endpoint de **gestion des sessions** (liste, révocation unitaire) : #117.
- Aucun endpoint de **gestion des rôles** : #115.
- Aucune **limitation de débit** : identifiée comme un risque, réduite par l'ordre d'exécution
  ci-dessus, et renvoyée à un ticket d'exploitation dédié.

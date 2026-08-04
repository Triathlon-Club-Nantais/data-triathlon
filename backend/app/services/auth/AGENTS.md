# Authentification (#114)
Socle SSO du back-office : ouvrir une session par délégation à GitHub, sans
jamais détenir de mot de passe, **et laisser le site public strictement intact**.
Spec, plan et tâches : `specs/20260801-145428-auth-socle-sso/` ; le sondage
`docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md` **prime** sur eux.

**Trois tables**, aucune existante modifiée. `users` (identité applicative),
`identities` (un moyen de se connecter), `user_sessions` (la preuve qu'un
navigateur agit pour un utilisateur). Trois invariants qu'on ne « corrige » pas :

- **`users.email` n'est pas unique** — une identité externe inconnue crée
  **toujours** un nouvel utilisateur, même si l'adresse est déjà en base.
  Apparier sur l'adresse rouvrirait la prise de contrôle par pré-inscription ;
- la **seule** clé de résolution est le couple `(provider, subject)` — ni
  l'adresse, ni le login du fournisseur, qui se renomme et redevient
  enregistrable par un tiers ;
- **`users` ne porte aucun rôle**, et n'en portera pas. Le rôle de #115 est
  relatif à une **organisation** — on est administrateur *d'un club*, pas
  administrateur tout court — et vivra dans une association
  `(user, organisation, role)`. Un scalaire `role` posé ici serait à défaire par
  une migration destructive au premier utilisateur ayant deux rôles dans deux
  clubs. C'est le même raisonnement qui place le futur mot de passe sur
  `identities` : ce qui est relatif à un tiers ne se met pas en colonne sur
  `users`. Un test le vérifie sur le schéma appliqué, pas seulement sur le modèle.

**Jeton opaque, empreinte en base.** Le cookie porte `secrets.token_urlsafe(32)`
(43 caractères) ; la base n'en garde que le SHA-256. Aucun sel, aucun KDF : ce
que bcrypt compense — faible entropie et dictionnaire — n'existe pas ici, et un
KDF coûterait à **chaque** requête authentifiée. C'est la **garde de longueur**
(`session.TOKEN_MIN_LENGTH`) qui rend SHA-256 nu suffisant, pas l'algorithme :
le jour où un code court entrerait dans la même colonne, elle deviendrait
cassable hors ligne. Une session est acceptée **si et seulement si** elle existe,
n'a pas expiré, et que son utilisateur est actif — la troisième condition est une
**jointure**, jamais un cache.

**Le registre vit dans `services/auth/idp/`**, et le nom est délibéré : « provider »
désigne déjà un **chronométreur** partout ailleurs (`PendingProvider`,
`--provider`, `PROVIDER_LABELS`, `GET /scrape/detect`). Employer le même mot
créerait un second sens et un second `registry.py` homonyme. Le contrat
`IdentityProvider` **n'énumère aucun mécanisme** : `authorize()` rend un
`round_trip` opaque que le flux signe sans le lire, ce qui permettra à OIDC d'y
ranger son `nonce` sans toucher au contrat, au flux, ni au fournisseur GitHub.
Une doublure de test ne s'enregistre **jamais** au niveau module — elle
existerait en production, et `is_configured()` est un garde de configuration,
pas un garde de sécurité.

**Huit réglages `AUTH_*`** (`backend/README.md` pour le tableau,
`docs/ci-cd.md` pour les valeurs par environnement) : `AUTH_SESSION_SECRET_KEY`
(≥ 32 caractères ou le démarrage échoue ; **vide = non configuré**, état
légitime), `AUTH_GITHUB_CLIENT_ID` / `_SECRET`, `AUTH_ALLOWED_EMAILS` (CSV,
**fail-closed** : vide interdit toute connexion et fait rendre `[]` à
`/auth/methods`), `AUTH_REDIRECT_BASE_URL` (origine de l'**interface**, jamais
celle de l'API, et **sans défaut**), `AUTH_COOKIE_SECURE` (dont le nom des
cookies est **dérivé** : `__Host-` exige `Secure`), `AUTH_SESSION_TTL_DAYS`,
`AUTH_STATE_TTL_SECONDS`.

Trois de ces réglages sont **transverses** — la clé de signature, la liste
d'autorisation et l'origine de retour —, et ce sont eux qu'éprouve
`Settings.auth_is_configured` ; les secrets d'un fournisseur restent derrière son
propre `is_configured()`. Les mêler masquerait un second fournisseur pourtant
configuré et obligerait à modifier ce garde à chaque ajout, ce que FR-033
proscrit. Les **deux** gardes sont éprouvées à l'entrée du parcours, socle
d'abord : sans la clé, `joserfc` levait un `ValueError` nu qui ressortait en
**500** — une page technique dans un navigateur en pleine navigation, là où le
contrat impose un 503 lisible.

`AUTH_REDIRECT_BASE_URL` est dans ce garde pour une raison mesurée : elle part
dans le `redirect_uri` enregistré chez le fournisseur. Avec un défaut localhost,
un déploiement qui l'oubliait paraissait **pleinement configuré** — la page de
connexion affichait son bouton — pendant que GitHub répondait par sa propre page
d'erreur. Le visiteur ne revenait jamais, aucun code de l'ensemble fermé ne se
déclenchait, et rien n'était journalisé côté backend.

**Une installation non configurée le dit au démarrage, en développement.** Sur
une base SQLite, `main._warn_if_auth_unconfigured` journalise les réglages
transverses absents et les fournisseurs non configurés — sans rien changer au
comportement, FR-036 restant intact. Le silence complet coûtait une session de
diagnostic : un `backend/.env` nommé `.env.local` (la convention du **frontend**)
n'est pas lu par `pydantic-settings`, et le seul symptôme était un
`/auth/methods` à `[]`. Le discriminant est `is_sqlite`, déjà employé comme garde
« environnement jetable » par `scripts/reset_db.py`, et **pas** un neuvième
réglage ; en production le silence est délibéré. L'avertissement nomme les
fournisseurs par leur **slug** seul : le contrat `IdentityProvider` n'énumère
aucun mécanisme, et deviner `AUTH_<SLUG>_CLIENT_ID` le replacerait dans l'usine.

**La garde `/admin` ne ferme que si une connexion est possible.** Sans les
secrets, `/auth/me` rend 401 pour tout le monde : rediriger ferait de cet écran,
ouvert jusqu'ici, une impasse pour **tous** — l'inverse de FR-036. Elle
distingue donc « anonyme avéré » (401) de « on ne sait pas » (backend
injoignable), et ne redirige que dans le premier cas, `/auth/methods` non vide.

**Aucune route existante n'est protégée** — c'est le périmètre de #115 —, et la
garde `frontend/app/admin/layout.tsx` est **d'interface seulement** : elle évite
d'exposer un écran inutilisable, elle ne protège aucune donnée. Deux tests le
verrouillent : l'un parcourt l'inventaire des routes et refuse tout 401/403,
l'autre interdit une dépendance globale sur l'application et sur les routers
existants. La protection future se posera **route par route**, jamais par un
`dependencies=` global qui fermerait le site public sans qu'on le voie.

**Toute sortie HTTP du parcours passe par `core.http.guarded_transport()`.**
`OAuth2Client` d'Authlib hérite de `httpx.Client`, donc `transport=` y descend
nativement. Le détecteur AST de `tests/test_core_http.py` a été **étendu** pour
le voir — il était aveugle aux liaisons d'`authlib.integrations.httpx_client` et
à `httpx.HTTPTransport`, soit la première sortie HTTP qui aurait échappé au
filet de #101, à l'endroit exact où circulent un `client_secret` et un code
d'autorisation. `services/auth/idp/github.py` est, avec `core/http.py`, le seul
fichier de son allowlist (`_FABRIQUES`), et l'exemption est doublée d'un test
positif : nominative, jamais un motif de dossier.

**L'ordre du retour de parcours est contractuel**, pas stylistique : validation
locale → effacement du cookie d'état → présence du `code` → réseau (FR-025). Le
limiteur de threads AnyIO est mesuré à **40** et toutes les routes du projet sont
`def` : un retour de parcours coûteux est un levier de déni de service **sur le
site public**. Un test vérifie qu'aucun octet ne part sur chacun des chemins
d'échec local. Tout échec **redirige** vers `/login?error=<code>`, où `<code>`
appartient à un ensemble **fermé** de cinq valeurs anglaises traduites par
l'interface — jamais un message du fournisseur ni une donnée d'entrée.

Trois points que le code ne dit pas :

- **La fermeture en masse des sessions est une procédure, pas un outil.** Pour
  **un compte** : `is_active = False` ferme immédiatement toutes ses sessions,
  l'invariant étant une jointure. Pour **tous** : supprimer toutes les lignes de
  `user_sessions`. Aucune commande CLI n'est livrée — le dépôt n'a aucun
  ordonnanceur, et une commande que personne ne lance ferait croire à une
  hygiène qui n'existe pas. Les sessions expirées sont purgées **opportunément**,
  à l'ouverture d'une session, pour le seul utilisateur concerné.
  **Cet argument ne couvre que l'hygiène**, pas la révocation d'urgence : en
  incident, la procédure suppose d'ouvrir `psql` sur Supabase à la main. Les deux
  besoins ont été fondus à tort ; le second est suivi en #169, hors périmètre.
- **L'adresse refusée est journalisée, la table des tentatives est écartée.**
  Un refus `account_not_allowed` trace l'adresse soumise dans les journaux du
  backend : sans elle, aucun refus n'est diagnosticable et l'exploitant ne sait
  pas quelle adresse ajouter. Une adresse n'est pas un secret au sens de FR-038,
  dont le filet porte sur les clés, les jetons et le code de retour. Le refus
  pour **adresse non certifiée** ne la journalise pas — le fournisseur ne la
  prouve pas. Consigner ces tentatives **en base** a été demandé en revue et
  écarté (suivi en #170, avec le passage de la liste d'autorisation en base) : ce
  serait la seule écriture pilotée par un visiteur non authentifié, sans plafond,
  sur de la donnée personnelle de tiers. Raisonnement complet :
  `specs/20260801-145428-auth-socle-sso/data-model.md`, §Ce qu'aucune table
  n'enregistre.
- **Une rotation de `AUTH_SESSION_SECRET_KEY` ne ferme aucune session.** Le
  jeton de session est **opaque et vérifié en base**, il n'est pas signé : la clé
  ne signe que le jeton d'état, donc une rotation n'interrompt que les parcours
  de connexion en cours. Croire l'inverse ferait tenir une fuite pour colmatée.
- **Le piège multi-worktree.** Une application OAuth GitHub n'accepte **qu'une
  seule** URL de retour, port compris, et `next dev` d'un second worktree
  atterrit sur `:3001` sans le dire. L'authentification n'est donc utilisable que
  depuis l'espace de travail principal. Corollaire pour `backend/.env`, que
  `.worktreeinclude` recopie : n'y figez ni `AUTH_REDIRECT_BASE_URL` ni les
  identifiants OAuth. Le retour vise l'**interface**
  (`<origine>/api/v1/auth/github/callback`) et jamais le backend — le cookie
  d'état est posé sur l'origine de l'interface, et un retour pointant sur le port
  du backend ferait échouer **tout** parcours en `state_mismatch`.


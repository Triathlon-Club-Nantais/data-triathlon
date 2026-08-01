# Research — Socle d'authentification SSO (#114)

Phase 0. Chaque décision porte son alternative rejetée. Les choix de bibliothèque ne sont **pas**
rejoués ici : ils sont tranchés sur mesures dans
[`docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md`](../../docs/superpowers/specs/2026-08-01-auth-librairies-sondage.md),
qui prime sur ce document.

## 1. Signature du contrat de fournisseur

**Decision** — le Protocol n'énumère pas les mécanismes. `authorize()` rend un
`AuthorizationRequest(url, round_trip)` où `round_trip` est un `Mapping[str, str]` **opaque** ; le
flux le signe et le restitue sans jamais le lire, et `fetch_identity()` le reçoit tel quel.

**Rationale** — c'est la seule forme qui survit au second fournisseur. Une signature
`authorize(..., verifier: str)` calquée sur PKCE oblige, à l'arrivée d'OIDC, à ajouter un `nonce`
aux deux méthodes, donc à modifier le contrat, le flux **et** le fournisseur GitHub existant. Avec
un aller-retour opaque, GitHub y range `{"verifier": …}`, un futur OIDC y rangera
`{"verifier": …, "nonce": …}`, et rien au-dessus ne bouge. Le `state` CSRF, lui, reste **commun** :
il est généré et comparé par le flux, jamais par un fournisseur — c'est une garantie du socle, pas
une variation de fournisseur.

**Alternatives considered** :
- **`verifier: str` en dur** — rejeté : fait fuiter le mécanisme de l'unique fournisseur dans le
  contrat censé l'abstraire, et casse au second.
- **Une méthode par mécanisme** (`supports_pkce()`, `build_nonce()`…) — rejeté : multiplie les
  points d'extension au lieu d'en fermer un.
- **Pas de Protocol du tout** — l'alternative sérieuse, portée en Complexity Tracking du plan et
  rejetée sur arbitrage utilisateur.

## 2. Transport de l'état du parcours

**Decision** — un cookie court (10 min), signé en JWS HS256 avec `joserfc`, portant
`{state, round_trip, provider}` et une expiration. `HttpOnly`, `Secure` en production,
`SameSite=Lax`. Consommé (effacé) **avant** l'échange de jeton, et effacé sur **tous** les chemins
de sortie du retour de parcours, succès compris.

**Rationale** — l'état ne crée aucune ligne en base, ce qui rend l'endpoint d'entrée quasi gratuit
et supprime tout levier de croissance illimitée par un anonyme. Le `provider` dans la charge signée
ferme la confusion de fournisseur : un état émis pour A n'est pas recevable au retour de B.
L'effacement **avant** l'échange donne l'usage unique sans table ni verrou : c'est le rejeu qui
alimenterait le déni de service décrit dans le sondage (limiteur de threads à 40).

**Alternatives considered** :
- **`itsdangerous`** (choix de la PR #159) — rejeté : `joserfc` arrive de toute façon avec Authlib
  et couvre le besoin (signature, expiration, rejet sur mauvaise clé, vérifié). Une dépendance
  directe de moins.
- **Table `oauth_states`** — rejeté : une table, une purge et un index de plus pour un objet qui
  vit dix minutes, alors qu'un cookie signé porte la même garantie.
- **Rien signer, comparer un opaque en session** — impossible : il n'y a pas de session avant la
  connexion.

## 3. Empreinte du jeton de session

**Decision** — SHA-256 nu du jeton, colonne unique et indexée. Aucun sel, aucun KDF. Une garde
refuse d'ouvrir une session sur un jeton de moins de 43 caractères.

**Rationale** — le jeton fait 256 bits uniformes (`secrets.token_urlsafe(32)`). Ce que bcrypt ou
argon2 compensent, c'est la **faible entropie** d'un mot de passe et l'existence d'un dictionnaire :
ni l'un ni l'autre n'existe ici, et un KDF coûterait à **chaque requête authentifiée** pour un gain
nul. La fragilité n'est pas cryptographique, elle est contractuelle — le jour où quelqu'un rangerait
un code court dans la même colonne, elle deviendrait cassable hors ligne sans qu'aucun test
n'échoue. D'où la garde de longueur, qui est la vraie protection, et le commentaire qui dit
*pourquoi* SHA-256 suffit.

**Alternatives considered** :
- **argon2 / bcrypt** — rejeté, coût par requête sans gain (voir ci-dessus).
- **HMAC avec un poivre serveur** — rejeté : ne gagne que si le générateur d'aléa est compromis,
  auquel cas la session n'est pas le premier problème.
- **Jeton en clair en base** (ce que fait une session signée sans stockage) — rejeté : c'est
  exactement la propriété qu'on achète en passant aux sessions serveur.

## 4. Résolution d'identité et liaison de comptes

**Decision** — la **seule** clé est `(provider, subject)`. L'adresse n'apparie jamais. Une identité
inconnue crée **toujours** un nouvel utilisateur, même si l'adresse est déjà connue. Aucune liaison
implicite, et aucun mécanisme de liaison explicite n'est livré.

**Rationale** — apparier sur l'adresse ouvre la prise de contrôle par **pré-inscription** : un
attaquant crée chez un fournisseur laxiste un compte portant l'adresse d'un contributeur, se
connecte, et sa propre identité se retrouve rattachée au compte de la victime — ou la victime au
sien. Le fait que GitHub certifie ses adresses ne protège pas : c'est un détail d'implémentation du
premier fournisseur, pas un contrat du socle. La PR #159 avait d'ailleurs la bonne intuition
(`email` délibérément non unique) ; le passage à `identities` la rendait facile à perdre de vue.

**Alternatives considered** :
- **Apparier sur l'adresse certifiée** — rejeté, vecteur ci-dessus.
- **Liaison explicite depuis une session ouverte** — bonne pratique, mais hors périmètre. Elle est
  **nommée comme absente** plutôt que passée sous silence, pour qu'on ne la croie pas acquise.

## 5. Certification de l'adresse et liste d'autorisation

**Decision** — `email_verified` fait partie du contrat `ExternalIdentity`. Le flux refuse une
adresse non certifiée **avant** d'examiner la liste d'autorisation. La liste porte sur l'adresse,
est **fail-closed** (vide = aucune connexion, et aucun moyen de connexion proposé), et est
réévaluée **à chaque connexion**.

**Rationale** — placer l'exigence de certification dans le contrat, et non dans le code du
fournisseur GitHub, est ce qui la rend opposable au fournisseur suivant. La posture fail-closed
n'est pas un excès de prudence : une variable absente sur Render est un incident ordinaire, et
« liste vide = tout le monde » transformerait cet incident en ouverture de l'administration à
n'importe quel compte GitHub. Deux notions cohabitent et doivent rester distinctes : la liste est
un **portail d'amorçage** réévalué à chaque connexion, l'autorisation durable étant `is_active`
puis le rôle (#115).

**Alternatives considered** :
- **Liste de logins GitHub** (choix de la PR #159) — rejeté : ne survit pas à un second fournisseur,
  et son argument de stabilité est faux — un login GitHub se renomme et l'ancien redevient
  enregistrable par un tiers. Le seul invariant stable est `(provider, subject)`, qui est déjà la
  clé.
- **Vide = tout accepté, « réservé au dev »** — rejeté : un commentaire n'est pas un mécanisme.
- **Pré-provisionner les utilisateurs par CLI** — rejeté ici : deux mécanismes d'autorisation qui
  se recouvrent finissent par diverger, ce que le dépôt a déjà payé (#76).

## 6. Attributs du cookie de session

**Decision** — préfixe `__Host-` en production, `Path=/`, pas d'attribut `Domain`, `HttpOnly`,
`Secure`, `SameSite=Lax`. Le nom est **dérivé** du réglage : sans `Secure` (développement en clair),
le préfixe est retiré, puisqu'il exige `Secure`.

**Rationale** — `SameSite` protège la **lecture** du cookie, jamais son **écriture**. Sans
`__Host-`, tout contenu exécuté sur un domaine apparenté peut poser un cookie de session et
provoquer une fixation — la victime navigue alors dans le compte de l'attaquant — ou injecter un
cookie d'état et rouvrir le CSRF de connexion. `vercel.app` figurant sur la Public Suffix List, la
production actuelle est protégée **par accident** ; brancher un domaine propre ferait tomber cette
protection. Le préfixe est en outre impossible à rétrofitter sans invalider toutes les sessions.

**Alternatives considered** :
- **`Path` restreint au chemin d'authentification** pour le cookie d'état (choix de la PR #159) —
  rejeté au profit de `__Host-`, incompatible avec un `Path` restreint : un chemin ne protège pas
  d'un sous-domaine, la non-écrasabilité si.
- **`SameSite=Strict`** — rejeté : casse le retour de navigation depuis le fournisseur.
- **`__Host-` conditionnel bricolé** — rejeté au profit d'un nom dérivé, explicite.

## 7. Restitution des échecs du retour de parcours

**Decision** — toute sortie en échec **redirige** vers `/login?error=<code>`, où `<code>` appartient
à un ensemble fermé de valeurs anglaises : `state_mismatch`, `email_unverified`,
`account_not_allowed`, `provider_error`, `provider_unavailable`. L'interface les traduit en
français. Aucune destination de retour n'est acceptée en paramètre.

**Rationale** — la PR #159 rend une page JSON brute à un navigateur en pleine navigation, et le
reconnaît en commentaire. L'ensemble fermé interdit qu'un message du fournisseur ou une donnée
d'entrée atteigne la page — la correction du défaut ne doit pas ouvrir une injection. Les codes sont
anglais comme tous les paramètres de query du dépôt (`scope`, `federal_only`, `seasons`) ; leur
libellé français vit dans l'interface, sur le modèle de `PROVIDER_LABELS`. Refuser toute destination
en paramètre ferme la redirection ouverte par construction : c'est le seul choix qui n'ait pas à
être validé correctement.

**Alternatives considered** :
- **Renvoyer le code de statut et le détail** — rejeté, c'est le défaut de #159.
- **Accepter un `?next=` validé** — rejeté : la validation correcte est difficile (`//evil.com`,
  `/\evil.com`, encodages, caractères de contrôle dans l'en-tête) et le besoin est absent tant que
  l'administration n'a qu'un écran.

## 8. Garantie de passage par le contrôle de destination

**Decision** — exposer `guarded_transport()` publiquement dans `app/core/http.py`, et **étendre le
détecteur AST existant** de `tests/test_core_http.py` pour qu'il voie les constructions
d'`OAuth2Client` et de `HTTPTransport`. Aucun second garde.

**Rationale** — mesuré : le détecteur rend `[]` sur `OAuth2Client(...)`, qu'il importe d'`authlib`
et non d'`httpx`, alors que la classe hérite de `httpx.Client` et ouvre de vraies connexions. Son
propre test de spécification asserte ce comportement (« un `Client` homonyme venu d'ailleurs »).
Introduire Authlib sans étendre le détecteur ajouterait à `app/` la **première** sortie HTTP que le
filet de #101 ne voit pas, à l'endroit exact où circulent un `client_secret` et un code
d'autorisation. Et `client()` rend un `httpx.Client` déjà construit : sans fabrique de transport
publique, il n'existe **aucune voie légale**, et la docstring de `client()` (« **Seule** voie de
sortie de `app/` ») deviendrait fausse.

**Alternatives considered** :
- **Un méta-test à l'exécution vérifiant que chaque fournisseur enregistré porte le transport
  gardé** — rejeté : c'est une **seconde définition** du même invariant, le motif exact de #33 et
  #76, et il ne verrait ni un second client interne, ni un fournisseur qu'on aurait oublié
  d'enregistrer. Le détecteur AST couvre tout `app/`.
- **Employer `_GuardTransport` directement** — rejeté : symbole privé.

## 9. Garde d'accès aux écrans d'administration

**Decision** — un `app/admin/layout.tsx` qui valide réellement la session côté serveur. Pas de
`middleware.ts`.

**Rationale** — un middleware ne peut que constater la **présence** du cookie, jamais sa validité :
il laisserait passer une session révoquée ou expirée. Et son `matcher`, s'il était mal borné,
intercepterait `/api/*`, cassant la réindirection vers le backend et le point d'entrée du cron
`keep-warm`. Un layout couvre en outre les futures sous-routes d'administration sans y penser.
Contrepartie assumée : `/admin`, aujourd'hui prérendue statiquement, devient dynamique — c'est
l'effet recherché.

**Alternatives considered** :
- **`middleware.ts`** — rejeté ci-dessus.
- **Garde dans la page** — rejeté : ne couvre pas les sous-routes à venir.

## 10. Lecture de la session dans l'interface

**Decision** — un hook TanStack Query sur `GET /api/v1/auth/me`. `serverFetch` est **inchangé** ; un
`serverFetchAuthed()` distinct est ajouté pour les rendus serveur qui ont besoin du cookie.

**Rationale** — appeler `cookies()` dans `app/layout.tsx` pour alimenter la topbar rendrait
**toute** l'application dynamique, le layout enveloppant chaque route : on paierait le prérendu
statique du site public pour afficher un avatar. TanStack est déjà monté. Et modifier `serverFetch`
toucherait les six pages publiques en rendu serveur, avec le même risque : d'où une fonction
séparée, au périmètre d'appel explicite.

**Alternatives considered** :
- **Session résolue dans le layout racine et passée en propriété** — rejeté ci-dessus.
- **Élargir `serverFetch` d'un paramètre optionnel** — rejeté : rend l'oubli facile dans les deux
  sens, et le risque porte sur des pages publiques.

## 11. Intégrité référentielle sur le rattachement à un athlète

**Decision** — pas d'`ON DELETE` au niveau de la base. La cascade est portée côté ORM, comme partout
ailleurs dans le dépôt.

**Rationale** — `app/core/database.py` n'émet aucun `PRAGMA foreign_keys=ON` : une contrainte
`ON DELETE` serait **inerte** en SQLite (développement et intégralité des tests) et **active** en
PostgreSQL. Une divergence dev/prod sur une règle d'intégrité est précisément ce qu'on ne veut pas
découvrir en production. Aucun modèle existant n'a d'`ondelete` ; ce n'est pas le rôle de cette
feature d'ouvrir ce chantier.

**Alternatives considered** :
- **`ON DELETE SET NULL`** (choix de la PR #159) — rejeté ci-dessus.
- **Activer le pragma** — rejeté : change le comportement de toutes les tables existantes, hors
  périmètre.

## 12. Isolation des tests vis-à-vis de la configuration locale

**Decision** — une fixture `autouse` sur le paquet de tests d'authentification, qui pose les
réglages par `monkeypatch.setenv` et appelle `get_settings.cache_clear()` **avant et après** chaque
test.

**Rationale** — `get_settings()` est `@lru_cache` et `Settings` lit `.env`. Un développeur ayant de
vrais secrets dans `backend/.env` verrait ses tests passer **pour la mauvaise raison**, pendant que
l'intégration continue, qui n'a pas de `.env`, diverge. Le dépôt a déjà ce motif exact dans
`tests/test_migrations.py`.

**Alternatives considered** :
- **Injecter les réglages par surcharge de dépendance FastAPI** — retenu **en plus**, pour les tests
  d'API ; insuffisant seul, les services lisant `get_settings()` hors requête.

## 13. Doublure de fournisseur en test

**Decision** — la doublure est enregistrée **par une fixture**, jamais au niveau du module. Un test
normatif vérifie que le registre importé à froid ne contient que GitHub.

**Rationale** — le registre des scrapers tient des singletons de module peuplés à l'import ; par
symétrie, une doublure enregistrée de la même façon **existerait en production**, et `is_configured()`
ne la masquerait que par configuration. Or `is_configured()` est un garde de configuration, pas un
garde de sécurité : il ne survit pas à une variable d'environnement traînante. Une doublure
atteignable en production est un contournement d'authentification complet — elle fabriquerait une
identité arbitraire.

**Alternatives considered** :
- **Enregistrement au module, masqué par `is_configured()`** — rejeté ci-dessus.
- **Garde `if environment != "production"`** — rejeté : le dépôt n'a pas de notion d'environnement,
  et l'introduire pour cela serait un mécanisme de plus à maintenir.

## 14. Purge des sessions expirées

**Decision** — suppression opportuniste des sessions expirées d'un utilisateur à l'ouverture d'une
session. Aucune commande CLI, aucun ordonnanceur.

**Rationale** — le dépôt n'a **aucun** ordonnanceur : le seul cron du projet est hébergé à
l'extérieur et vise une route de l'interface. Une commande de purge ne serait lancée par personne,
et ferait croire à une hygiène qui n'existe pas. Une session expirée est déjà refusée en lecture
(FR-013) : sa suppression physique est de l'hygiène, pas de la sécurité.

**Alternatives considered** :
- **Commande CLI `purge-sessions`** — rejeté ci-dessus. Si elle devenait nécessaire, elle devrait
  suivre les conventions du dépôt : couche mince, `emit_report` (c'est un inventaire, pas un batch
  à échec partiel), unité nommée dans chaque libellé, stdout pur sous `--json`.
- **Tâche périodique dans l'application** — rejeté : un processus de fond dans une application web
  déployée sur un service qui s'endort.

## 15. Durée et renouvellement de session

**Decision** — 7 jours, sans prolongation glissante, sans date de dernière activité.

**Rationale** — repris de la PR #159, qui l'avait bien arbitré. Sans plafond absolu, une
prolongation glissante rend un jeton volé indéfiniment renouvelable. Et une date de dernière
activité coûterait une écriture à **chaque** requête authentifiée, sur Supabase, pour zéro lecteur —
elle relève de l'écran « mes sessions » (#117), et s'ajoutera alors par migration purement
additive.

**Alternatives considered** :
- **Fenêtre glissante** — rejeté ci-dessus.
- **Durée de session navigateur** — rejeté : incompatible avec l'exigence de survie à la fermeture
  de l'onglet (FR de la User Story 1).

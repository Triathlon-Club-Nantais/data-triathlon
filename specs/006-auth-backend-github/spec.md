# Feature Specification: Authentification GitHub OAuth pour le back-office admin

**Feature Branch**: `worktree-114-auth-backend`

**Created**: 2026-07-31

**Status**: Draft

**Input**: Sous-issue #114 de l'épique #81 (Panel Admin). Fournir un socle d'authentification OIDC (GitHub OAuth) pour le back-office, sans dégrader l'accès public.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un administrateur pressenti s'authentifie via GitHub (Priority: P1)

Un contributeur du club, invité à administrer le site TCN, ouvre l'application et déclenche la connexion « Se connecter avec GitHub ». Il est redirigé vers GitHub, autorise l'application, revient sur le site avec une session ouverte. Il est reconnu par le système comme un utilisateur applicatif, sans rôle particulier pour l'instant — le socle d'authentification ne débloque aucune action admin, ce que fera la sous-issue suivante (#115, RBAC).

**Why this priority**: C'est le socle. Sans lui, aucune des cinq autres sous-issues de l'épique #81 ne peut avancer. Ce ticket est explicitement listé comme « le socle — bloque toutes les autres sous-issues ».

**Independent Test**: Peut être validé de bout en bout en configurant une application OAuth GitHub, en lançant le backend, en visitant `/api/v1/auth/github/authorize`, et en constatant qu'après retour du callback (a) un utilisateur est créé/retrouvé en base et (b) `GET /api/v1/auth/me` répond avec ses informations. Un test d'intégration mockant GitHub via `httpx` valide le flux sans réseau.

**Acceptance Scenarios**:

1. **Given** aucun utilisateur applicatif n'existe et le contributeur a un compte GitHub valide, **When** il complète le flux d'autorisation GitHub, **Then** une fiche utilisateur est créée (email, identifiant GitHub, login GitHub, actif) et une session est ouverte via un cookie signé.
2. **Given** un utilisateur existe déjà avec ce même identifiant GitHub, **When** il complète à nouveau le flux d'autorisation, **Then** aucune fiche en double n'est créée et une nouvelle session est ouverte pour la fiche existante.
3. **Given** une session est ouverte, **When** l'utilisateur appelle `GET /api/v1/auth/me`, **Then** l'API renvoie ses informations (email, identifiant GitHub, login) avec un code HTTP 200.
4. **Given** une session est ouverte, **When** l'utilisateur appelle `POST /api/v1/auth/logout`, **Then** le cookie de session est invalidé et un appel ultérieur à `/api/v1/auth/me` renvoie 401.

---

### User Story 2 - Le site public reste 100 % accessible sans connexion (Priority: P1)

Un visiteur anonyme (membre du club consultant les résultats, ou toute personne curieuse) navigue sur le site sans se connecter. Il consulte les épreuves, les classements, la carte, le dashboard, et peut ajouter une épreuve par URL — exactement comme aujourd'hui. Aucune régression fonctionnelle, aucune redirection vers un écran de connexion, aucun message d'erreur d'autorisation.

**Why this priority**: Contrainte structurante de l'épique #81 (« Accès public inchangé »). C'est cette contrainte qui interdit d'apposer une protection globale sur `/api/v1/*` et qui exige de traiter la dépendance `get_current_user` comme optionnelle sur les routes existantes.

**Independent Test**: Une suite de tests API rejoue les endpoints publics existants (`/api/v1/courses/*`, `/api/v1/athletes/*`, `/api/v1/scrape/*`, `/api/v1/stats/*`, `/api/v1/geocode/*`) sans cookie de session et vérifie qu'ils répondent 200 comme avant l'introduction de l'auth.

**Acceptance Scenarios**:

1. **Given** aucun cookie de session n'est présent, **When** un client anonyme appelle un endpoint public existant, **Then** l'endpoint répond exactement comme avant l'introduction de l'auth (mêmes codes, mêmes charges utiles).
2. **Given** un utilisateur non authentifié, **When** il appelle `GET /api/v1/auth/me`, **Then** l'API répond 401 (et non 500 ou une redirection).
3. **Given** l'application vient d'être déployée sans que `GITHUB_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_SECRET` / `SESSION_SECRET_KEY` soient définis, **When** un client anonyme appelle un endpoint public, **Then** l'endpoint répond normalement. L'authentification GitHub, elle, est indisponible (les routes `/api/v1/auth/github/*` renvoient une erreur de configuration explicite) mais cela ne bloque en rien la lecture publique.

---

### User Story 3 - Un attaquant ne peut pas détourner le flux OAuth (Priority: P2)

Un tiers hostile tente d'exploiter la surface d'authentification : rejeu d'un `code` GitHub, forge d'un cookie de session, callback avec un `state` inconnu, code GitHub invalide. Le système refuse toutes ces tentatives et n'ouvre pas de session frauduleuse.

**Why this priority**: L'authentification est par nature une surface d'attaque. Un flux OAuth mal implémenté peut mener à une prise de compte silencieuse. C'est P2 (non pas P1) parce que le périmètre de #114 n'est **pas** un panneau admin exposant des actions destructrices — sans RBAC, un compte utilisateur ouvert n'a accès à rien de plus qu'un anonyme.

**Independent Test**: Une suite de tests unitaires simule chaque cas d'attaque (state absent/inconnu, code invalide, cookie non signé, cookie signé mais expiré, cookie signé par une clé antérieure) et vérifie la réponse attendue (400, 401, ou pas d'ouverture de session).

**Acceptance Scenarios**:

1. **Given** un attaquant appelle `/api/v1/auth/github/callback?code=…&state=inconnu`, **When** le backend traite l'appel, **Then** la requête est rejetée avec un message d'erreur clair et aucune session n'est ouverte.
2. **Given** un attaquant forge un cookie de session avec un `user_id` valide mais une signature invalide, **When** il appelle `GET /api/v1/auth/me`, **Then** l'API répond 401 et considère le client comme anonyme.
3. **Given** un cookie de session légitime a expiré (âge supérieur à la durée maximum configurée), **When** son porteur appelle `GET /api/v1/auth/me`, **Then** l'API répond 401.
4. **Given** `SESSION_SECRET_KEY` a été rotée, **When** un porteur de cookie signé par l'ancienne clé appelle un endpoint, **Then** l'API répond 401 (rotation = invalidation implicite des sessions en cours, comportement documenté).

---

### Edge Cases

- **GitHub renvoie un utilisateur sans email public** : l'API GitHub `/user` peut renvoyer `email: null` si l'utilisateur a masqué son adresse principale. Le système récupère alors le premier email vérifié depuis `/user/emails` (scope `user:email` demandé lors de l'autorisation). Si aucun email vérifié n'est disponible, la fiche utilisateur est refusée avec un message français expliquant qu'un email GitHub vérifié est requis.
- **Utilisateur déjà présent en base avec un email identique mais un identifiant GitHub différent** : la fiche existante n'est **pas** écrasée. L'unicité applicative est portée par `github_id`, pas par `email` (un même humain peut légitimement changer d'email GitHub). Le nouvel identifiant GitHub crée une seconde fiche utilisateur ; le rapprochement éventuel est un sujet d'administration (hors #114).
- **Rotation de `SESSION_SECRET_KEY`** : toutes les sessions en cours sont invalidées, les utilisateurs doivent se reconnecter. Documenté ; pas de mécanisme de « clés précédentes » sur ce ticket (à re-considérer en #116 si l'UX l'exige).
- **Requête `POST /api/v1/auth/logout` sans session** : l'endpoint répond 204 (No Content) — la déconnexion d'un anonyme est un no-op, pas une erreur.
- **Callback GitHub avec un `code` déjà consommé** : GitHub renvoie une erreur qui remonte telle quelle sous forme d'une réponse HTTP 400 côté TCN. Aucune session n'est ouverte.
- **Environnement de développement local sans HTTPS** : `Secure` désactivé conditionnellement quand la configuration explicite l'autorise (variable dédiée) — un cookie `Secure` sur `http://localhost` serait ignoré par le navigateur, l'auth ne fonctionnerait pas en dev.

## Requirements *(mandatory)*

### Functional Requirements

**Authentification**

- **FR-001**: Le système DOIT exposer un endpoint qui redirige l'utilisateur vers l'écran d'autorisation GitHub, en incluant un paramètre `state` cryptographiquement aléatoire à usage unique servant de protection CSRF.
- **FR-002**: Le système DOIT exposer un endpoint de callback qui, à réception d'un `code` et d'un `state` valides, échange le code contre un jeton d'accès GitHub, récupère l'identité de l'utilisateur (`id`, `login`, email vérifié), et ouvre une session applicative.
- **FR-003**: Le système DOIT rejeter tout callback dont le `state` est absent, inconnu, expiré, ou déjà consommé, sans ouvrir de session.
- **FR-004**: Le système DOIT rejeter tout callback dont le `code` est refusé par GitHub, sans ouvrir de session, et exposer un message d'erreur explicite en français à destination de l'utilisateur.
- **FR-005**: Le système DOIT récupérer un email GitHub vérifié pour chaque nouvelle fiche utilisateur ; si aucun email vérifié n'est disponible, la création est refusée avec un message français explicite.

**Fiche utilisateur**

- **FR-006**: Le système DOIT persister, pour chaque utilisateur, au moins : identifiant GitHub numérique (unique), login GitHub, email, indicateur d'activité, date de création, référence optionnelle vers un athlète.
- **FR-007**: Le système DOIT garantir l'unicité de l'identifiant GitHub numérique — deux fiches utilisateur ne peuvent pas partager le même identifiant GitHub.
- **FR-008**: Le système NE DOIT PAS stocker de mot de passe, de secret partagé, ni le jeton d'accès GitHub après le callback (le jeton sert uniquement à récupérer l'identité et est immédiatement oublié).
- **FR-009**: Le système DOIT réutiliser la fiche existante d'un utilisateur qui se reconnecte (identification par identifiant GitHub numérique).
- **FR-010**: Le système NE DOIT PAS écraser silencieusement une fiche utilisateur au callback : login et email peuvent évoluer côté GitHub, mais toute divergence sur l'identifiant GitHub numérique crée une fiche distincte.

**Session**

- **FR-011**: Le système DOIT ouvrir la session en posant un cookie signé côté serveur, marqué `HttpOnly`, `SameSite=Lax`, et `Secure` en production. Le cookie DOIT porter l'identifiant de l'utilisateur applicatif et une horodate d'émission.
- **FR-012**: Le système DOIT rejeter tout cookie de session dont la signature est invalide, dont l'horodate est plus ancienne que la durée maximum configurée, ou dont la clé de signature n'est plus reconnue.
- **FR-013**: Le système DOIT exposer un endpoint permettant à l'utilisateur de fermer sa session, qui invalide le cookie (positionne une valeur expirée).
- **FR-014**: L'endpoint de fermeture de session DOIT répondre 204 sans erreur même en l'absence de session (déconnexion d'un anonyme = no-op).

**Introspection**

- **FR-015**: Le système DOIT exposer un endpoint qui, si une session valide est présentée, renvoie les informations publiques de l'utilisateur (identifiant applicatif, email, login GitHub) ; sinon, répond 401.
- **FR-016**: Le système DOIT fournir un mécanisme réutilisable par les routes futures pour reconnaître un utilisateur authentifié — soit exiger une session (401 si absente), soit l'accepter en option (utilisateur anonyme accepté).

**Non-régression du site public**

- **FR-017**: Le système NE DOIT PAS appliquer de contrôle d'authentification global. Les endpoints publics existants (courses, athlètes, scrape, stats, geocode) DOIVENT continuer de répondre sans session comme aujourd'hui.
- **FR-018**: L'introduction du modèle utilisateur NE DOIT PAS modifier les colonnes, contraintes, ou index existants des tables actuelles.

**Configuration et secrets**

- **FR-019**: Les paramètres d'authentification (identifiant client GitHub, secret client GitHub, clé de signature de session, durée de session, indicateur de mode « développement » désactivant `Secure`) DOIVENT être configurables par variable d'environnement, jamais commités en clair, et documentés dans le fichier d'exemple.
- **FR-020**: L'absence des secrets GitHub à l'exécution NE DOIT PAS empêcher l'application de démarrer ni de servir les endpoints publics ; seuls les endpoints d'authentification GitHub deviennent indisponibles avec une erreur explicite.

**Constitution v1.0.0**

- **FR-021**: Les messages d'erreur destinés à l'utilisateur (relayés via l'exception métier française du projet) DOIVENT être en français. Les logs applicatifs et les identifiants techniques DOIVENT être en anglais.
- **FR-022**: L'accès à la base de données pour la lecture et l'écriture de la fiche utilisateur DOIT passer par un repository dédié — aucun accès de session SQL n'est autorisé dans le router ni dans le service.
- **FR-023**: Les endpoints d'authentification DOIVENT être versionnés sous le préfixe existant `/api/v1/`.

### Key Entities *(include if feature involves data)*

- **User** : fiche applicative d'un contributeur du back-office. Attributs métier : identifiant applicatif, identifiant GitHub numérique (unique), login GitHub, email, indicateur d'activité, date de création, référence optionnelle vers un athlète. **Aucune** notion de rôle sur ce ticket — reportée à #115.
- **Session (implicite dans le cookie)** : identifiant de l'utilisateur applicatif + horodate d'émission, signés par une clé serveur. Aucune persistance en base sur ce ticket (le cookie signé fait autorité). Une éventuelle table `sessions` reste ouverte pour la révocation, sortie du périmètre de #114.
- **State CSRF (implicite)** : jeton aléatoire à usage unique, émis à l'entrée du flux d'autorisation, exigé au retour du callback. Sa portée de vie couvre uniquement le temps du round-trip GitHub — pas de persistance longue durée.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % des endpoints publics existants (courses, athlètes, scrape, stats, geocode) répondent sans authentification, dans une suite de non-régression automatisée ajoutée à ce ticket.
- **SC-002**: Un contributeur reçu comme testeur peut compléter le flux « je clique sur Se connecter avec GitHub → je reviens sur le site connecté » en moins d'une minute sur un poste où il est déjà authentifié GitHub, sans lire de documentation.
- **SC-003**: 0 secret d'authentification commité dans l'historique git (vérifié par une lecture ciblée du diff avant merge).
- **SC-004**: La suite de tests unitaires couvre au moins : (a) émission et vérification du cookie signé (succès, signature invalide, expiration, clé rotée), (b) le callback GitHub réussi, (c) le callback GitHub refusé (state absent, state inconnu, code invalide, email absent), (d) la dépendance qui exige une session (401 sans, 200 avec), (e) la dépendance qui l'accepte en option (200 sans, 200 avec).
- **SC-005**: L'ajout du modèle utilisateur ne casse aucun test existant du backend (`uv run pytest -m "not integration"` passe entièrement).
- **SC-006**: La ligne de flottaison financière est nulle : le projet n'ajoute aucun service payant ni aucun compte partagé — l'application OAuth GitHub est gratuite et créée par l'administrateur du dépôt.

## Assumptions

- **Périmètre backend strict** : ce ticket ne livre **aucun** écran, aucun bouton, aucune UI. L'écran de connexion et la gestion de session côté Next.js sont dans la sous-issue #116, qui dépend du contrat de cookie défini ici.
- **Pas de RBAC** : tout utilisateur authentifié est reconnu, mais aucun rôle n'est stocké sur ce ticket. #115 ajoutera le champ de rôle, la commande CLI de bootstrap admin, et les dépendances `require_role`.
- **Un seul provider OIDC** : GitHub OAuth. Pas de Google Workspace, pas de fallback login/password local. Ce choix a été explicitement pris et documenté à l'ouverture de #114 — s'il devait évoluer, ce serait un ticket séparé (nouveau provider), pas une évolution de #114.
- **Cible utilisateur** : un petit cercle (moins d'une dizaine à moyen terme) de contributeurs du club, tous porteurs d'un compte GitHub. L'inscription publique n'est pas un cas d'usage — seule la première connexion sert d'inscription implicite.
- **Session dans un cookie signé, pas de table de sessions** : la révocation immédiate (au-delà de l'expiration) n'est pas un besoin identifié à ce jour. Si elle le devient (fuite de cookie constatée, poste compromis), l'ajout d'une table `sessions` ou d'une rotation de `SESSION_SECRET_KEY` sont deux réponses documentées.
- **URL de retour du callback** : une seule URL de callback, configurée statiquement, pointant vers le domaine du backend TCN. La destination finale après retour (par exemple `/admin` en local, `/` en production tant qu'aucun back-office n'est livré) est portée par une variable de configuration, pas par un paramètre d'entrée du callback — un paramètre d'entrée serait une porte ouverte à l'« open redirect ».
- **Environnement de développement** : le cookie `Secure` est désactivable via une variable de configuration, sinon l'auth ne fonctionne pas sur `http://localhost`. Cette variable est **absente** de la production Render et de Vercel — elle est un signal développement, pas un interrupteur d'exploitation.
- **Aucune atteinte à la base existante** : les modèles `Athlete`, `Course`, `Participation`, `PendingProvider` ne sont pas modifiés. Une migration Alembic ajoute la table `users` et, si nécessaire pour la FK, une clé étrangère nullable — sans transformation des données existantes.

# Phase 0 — Research

Aucun `NEEDS CLARIFICATION` dans le Technical Context : la demande d'entrée
posait déjà les contraintes de sécurité. Ce document consigne les décisions
de conception plus fines.

## D1 — Hachage : `hashlib.scrypt` (stdlib), pas de nouvelle dépendance

**Décision** : le mot de passe est haché avec `hashlib.scrypt` (module
standard de Python depuis 3.6, fonction de dérivation de clé memory-hard,
paramétrable en coût CPU/mémoire), avec un sel aléatoire de 16 octets
(`secrets.token_bytes`) généré à **chaque** remplacement. Hache et sel sont
stockés séparément, tous deux en hexadécimal.

**Rationale** :
- **Aucune dépendance ajoutée** — le dépôt n'a ni `bcrypt`, ni `argon2-cffi`,
  ni `passlib` en dépendance aujourd'hui (`grep` sur `pyproject.toml` :
  aucune correspondance). Principe VI et la règle « s'appuyer d'abord sur
  les dépendances déjà présentes » : `scrypt` est déjà dans la bibliothèque
  standard, memory-hard comme `argon2` (contrairement à un simple
  PBKDF2-HMAC, vulnérable à l'accélération GPU/ASIC à coût égal), et évite
  d'introduire un paquet tiers pour un besoin que le stdlib couvre déjà.
- **Comparaison en temps constant** à la vérification
  (`hmac.compare_digest` sur les deux empreintes hexadécimales), même
  patron que la comparaison du mot de passe déjà en place pour #271.

**Alternatives rejetées** :
- *`bcrypt`/`argon2-cffi`* — solutions établies et éprouvées, mais
  ajouteraient une dépendance pour un besoin que `scrypt` (stdlib) couvre
  déjà avec les mêmes garanties (memory-hard, sel intégré au processus de
  dérivation).
- *SHA-256 simple + sel* (le patron déjà utilisé pour les jetons de session
  SSO, `services/auth/session.py`) — **délibérément écarté ici** : un jeton
  de session est un secret à haute entropie généré par le serveur
  (`secrets.token_urlsafe(32)`, 256 bits uniformes), qu'un simple hachage
  suffit à protéger (`services/auth/session.py` le documente explicitement).
  Un mot de passe **choisi par un humain** (Story 1) a une entropie très
  inférieure et devient attaquable hors ligne par force brute sur un simple
  hachage rapide — c'est précisément le cas que `scrypt` couvre et que
  SHA-256 nu ne couvre pas.

## D2 — Secret de session distinct, tourné à chaque changement de mot de passe

**Décision** : une nouvelle valeur, `session_secret` (aléatoire,
`secrets.token_urlsafe(32)`), est stockée aux côtés du hachage et régénérée
à **chaque** remplacement du mot de passe (saisie ou génération). C'est
cette valeur — pas le mot de passe — qui sert de clé HMAC pour signer et
vérifier le cookie de session bénévole (`sign_session`/`verify_session`,
déjà écrits pour #271, **inchangés dans leur signature** : ils prennent déjà
une clé générique en paramètre, seule la valeur passée change).

**Rationale** :
- **Le mécanisme actuel (#271) est incompatible avec un hachage à sens
  unique.** Aujourd'hui, le cookie est signé avec le mot de passe **en
  clair** lui-même comme clé HMAC, et la vérification recalcule ce HMAC
  avec le mot de passe courant relu depuis la configuration — cela suppose
  que le serveur puisse toujours relire le mot de passe en clair, ce
  qu'interdit justement le hachage à sens unique demandé ici (FR-004).
- **Préserve la propriété de révocation collective d'#271** sans jamais
  avoir besoin du mot de passe en clair : changer le mot de passe régénère
  ce secret, ce qui invalide tous les cookies existants d'un coup — exactement
  le même comportement observable qu'#271 avait choisi (research.md §D1 de
  cette feature-là), obtenu autrement.
- **Aucune nouvelle table de sessions** : la propriété reste stateless côté
  cookie, seule la clé de vérification change de nature (secret dédié au
  lieu du mot de passe).

**Alternatives rejetées** :
- *Dériver le secret de session du hachage du mot de passe* (ex. HMAC du
  hachage) — techniquement possible, mais couple la sécurité du cookie à un
  détail d'implémentation du hachage (paramètres de coût `scrypt`) sans
  bénéfice : un secret aléatoire indépendant est plus simple à raisonner et
  aussi robuste.
- *Table de sessions bénévoles avec révocation individuelle* — déjà
  rejetée par #271 (research.md §D1 de cette feature-là) pour la même
  raison : aucune identité individuelle à révoquer, la rotation collective
  suffit au besoin exprimé.

## D3 — Stockage : une nouvelle table à une seule ligne

**Décision** : une table dédiée, `benevole_access_config`
(`BenevoleAccessConfig`), portant `password_hash`, `password_salt`,
`session_secret`, `updated_at`, `updated_by_user_id` (FK `users.id`). **Une
seule ligne existe à tout instant** — le remplacement du mot de passe est un
`UPDATE` de cette ligne si elle existe, ou son unique `INSERT` sinon.
**Absence de ligne = non configuré** (fail-closed, FR-007), sans distinguer
« jamais configuré » d'un état particulier — c'est exactement le même
prédicat qu'aujourd'hui (`BENEVOLE_SHARED_PASSWORD` vide).

**Rationale** :
- Aucune table générique de configuration clé-valeur n'existe dans ce dépôt
  (`ls app/models/` : aucun `settings`/`config` générique) — introduire une
  telle table pour un seul cas d'usage serait une abstraction spéculative
  que le Principe VI proscrit. Une table nommée pour son objet, sur le
  patron de toutes les autres tables du dépôt, est plus simple à lire.
- Une seule ligne, jamais une table de configurations versionnées ou
  historisées : rien dans la spec ne demande de conserver les anciens mots
  de passe (au contraire, FR-004 l'interdit), et un historique ajouterait
  une surface où un ancien hachage pourrait fuiter par erreur applicative.

## D4 — Pouvoir RBAC dédié, dans le regroupement « Rôles et accès »

**Décision** : un nouveau pouvoir, `benevole_access:manage`, dans
`core/permissions.py`, sous `FEATURE_ROLES` (« Rôles et accès ») — le même
regroupement que `allowed_emails:manage` et `sessions:revoke`, les deux
pouvoirs déjà les plus proches par leur nature (gérer un mécanisme d'accès
transverse, pas une ressource métier).

**Rationale** : suit exactement le modèle déjà en place (#115) — un pouvoir,
un code anglais stable, vérifié par `require_permission(P.BENEVOLE_ACCESS_MANAGE)`
posé route par route (jamais par préfixe). Un seul pouvoir couvre à la fois
la lecture de l'état (FR-005 : « consulter... ou la modifier ») et
l'écriture — la spec ne distingue pas ces deux gestes en deux pouvoirs
séparés, contrairement à `sessions:revoke` (un seul geste) mais à
l'instar d'`allowed_emails:manage` (lecture + écriture sous le même code).

**Alternatives rejetées** :
- *Réutiliser un pouvoir existant* (`sessions:revoke` ou
  `allowed_emails:manage`) — rejeté : FR-005 exige un pouvoir **distinct**
  des pouvoirs déjà existants, et mélanger cette gestion à une ressource qui
  n'a rien à voir avec les bénévoles rendrait le catalogue moins lisible.

## D5 — Transport du mot de passe généré : une seule réponse HTTP, jamais persisté

**Décision** : `POST /admin/benevoles/access/generate` génère le mot de
passe côté serveur (`secrets.token_urlsafe`), le hache et le stocke
immédiatement (comme pour une saisie manuelle), puis renvoie le mot de passe
**en clair** dans le corps de cette unique réponse HTTP. Rien côté serveur
ne le conserve après la génération du hachage — aucune variable de session,
aucun cache, aucun fichier temporaire.

**Rationale** : FR-003 exige qu'il soit « affiché une seule fois,
immédiatement après sa génération » — la réponse HTTP de la requête qui l'a
généré est le seul véhicule qui satisfait cette exigence sans introduire un
état intermédiaire (ex. un jeton à usage unique pour le récupérer une
seconde fois) qui recréerait exactement le risque que FR-004 interdit.

**Longueur** : `secrets.token_urlsafe(18)` rend 24 caractères pour 144 bits
d'entropie uniforme — trop pour un humain à retenir, ce qui est le but
(Story 2 vise un secret robuste, pas mémorisable) ; largement au-dessus de
ce qu'impose une contrainte de longueur minimale sur la saisie manuelle
(Story 1, cf. `data-model.md`).
